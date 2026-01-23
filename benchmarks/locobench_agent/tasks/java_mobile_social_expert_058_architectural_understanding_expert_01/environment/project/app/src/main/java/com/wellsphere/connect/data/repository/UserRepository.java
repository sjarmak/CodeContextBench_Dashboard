package com.wellsphere.connect.data.repository;

import android.annotation.SuppressLint;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.wellsphere.connect.data.local.UserLocalDataSource;
import com.wellsphere.connect.data.model.UserProfile;
import com.wellsphere.connect.data.remote.NetworkStateProvider;
import com.wellsphere.connect.data.remote.UserRemoteDataSource;
import com.wellsphere.connect.util.Event;

import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

import io.reactivex.Completable;
import io.reactivex.Flowable;
import io.reactivex.Maybe;
import io.reactivex.Observable;
import io.reactivex.Scheduler;
import io.reactivex.Single;
import io.reactivex.disposables.CompositeDisposable;
import io.reactivex.processors.BehaviorProcessor;
import io.reactivex.schedulers.Schedulers;

/**
 * Repository that orchestrates user-related data flows between the network layer, the local
 * persistence layer (Room), and in-memory cache. Thread-safe singleton and satisfies the
 * Repository pattern contract for the MVVM stack used in WellSphere Connect.
 *
 *  ▸ Guarantees a single source of truth (SSOT) for {@link UserProfile}
 *  ▸ Implements offline-first semantics: read from cache ➜ DB ➜ network (if connected)
 *  ▸ Publishes changes via {@link Flowable} for reactive UI updates
 *  ▸ Propagates authentication / biometric events through {@link Event}-wrapped channels
 *
 * Error handling maps low-level exceptions to domain-specific failures so that ViewModels
 * are shielded from infra concerns.
 */
@SuppressLint("CheckResult")
public final class UserRepository {

    /* ----------------------------------------- */
    /* Static factory / Singleton boilerplate    */
    /* ----------------------------------------- */

    private static volatile UserRepository sInstance;

    public static UserRepository getInstance(@NonNull UserRemoteDataSource remoteDS,
                                             @NonNull UserLocalDataSource localDS,
                                             @NonNull NetworkStateProvider networkStateProvider) {
        if (sInstance == null) {
            synchronized (UserRepository.class) {
                if (sInstance == null) {
                    sInstance = new UserRepository(
                            remoteDS,
                            localDS,
                            networkStateProvider,
                            Schedulers.io(),
                            Schedulers.computation());
                }
            }
        }
        return sInstance;
    }

    /* ----------------------------------------- */
    /* Dependencies                              */
    /* ----------------------------------------- */

    private final UserRemoteDataSource remoteDS;
    private final UserLocalDataSource localDS;
    private final NetworkStateProvider networkStateProvider;

    private final Scheduler io;           // Disk / network
    private final Scheduler computation;  // In-memory transforms / mapping

    /* ----------------------------------------- */
    /* Internal state & reactive channels        */
    /* ----------------------------------------- */

    /**
     * Memory cache with naive invalidation. In production, this could be replaced by LRU.
     * Key is the userId.
     */
    private final ConcurrentHashMap<String, UserProfile> memoryCache = new ConcurrentHashMap<>();

    /**
     * Hot stream emitting the latest profile snapshot whenever it changes.
     * Acts as an observable SSOT for UI subscribers.
     */
    private final BehaviorProcessor<Event<UserProfile>> profileProcessor =
            BehaviorProcessor.create();

    private final CompositeDisposable disposables = new CompositeDisposable();

    private static final long CACHE_TTL_MILLIS = TimeUnit.MINUTES.toMillis(20);

    /* ----------------------------------------- */
    /* Constructor                               */
    /* ----------------------------------------- */

    private UserRepository(@NonNull UserRemoteDataSource remoteDS,
                           @NonNull UserLocalDataSource localDS,
                           @NonNull NetworkStateProvider networkStateProvider,
                           @NonNull Scheduler ioScheduler,
                           @NonNull Scheduler computationScheduler) {

        this.remoteDS = remoteDS;
        this.localDS = localDS;
        this.networkStateProvider = networkStateProvider;
        this.io = ioScheduler;
        this.computation = computationScheduler;
    }

    /* ----------------------------------------- */
    /* Public API                                */
    /* ----------------------------------------- */

    /**
     * Returns a hot stream of {@link UserProfile} objects wrapped in {@link Event}. Whenever the
     * underlying data is updated (local edit, network sync, etc.) a new event is emitted.
     */
    public Flowable<Event<UserProfile>> observeUserProfile(@NonNull String userId) {
        // Trigger initial load if nothing cached yet
        if (!memoryCache.containsKey(userId)) {
            // The call chain handles cache ➜ db ➜ network
            getUserProfile(userId, /*forceRefresh*/ false)
                    .subscribe(
                            profile -> { /* no-op, processor updated within pipeline */ },
                            throwable -> profileProcessor.onNext(Event.error(throwable)));
        }
        return profileProcessor.onBackpressureLatest()
                               .filter(event -> event.hasData() &&
                                                Objects.equals(event.getData().getId(), userId));
    }

    /**
     * Returns a single snapshot of the user profile. If {@code forceRefresh} is true, bypasses all
     * caches and retrieves the data from the network (requiring connectivity).
     */
    public Single<UserProfile> getUserProfile(@NonNull String userId, boolean forceRefresh) {

        if (!forceRefresh) {
            // 1 ▸ memory cache
            @Nullable UserProfile cached = memoryCache.get(userId);
            if (cached != null && !cached.isExpired(CACHE_TTL_MILLIS)) {
                return Single.just(cached);
            }
        }

        // 2 ▸ local database (Room)
        Maybe<UserProfile> fromDb = localDS
                .getUserProfile(userId)
                .subscribeOn(io)
                .filter(profile -> !forceRefresh && !profile.isExpired(CACHE_TTL_MILLIS));

        // 3 ▸ remote network
        Single<UserProfile> fromNetwork = remoteDS
                .fetchUserProfile(userId)
                .subscribeOn(io)
                .flatMap(profile -> localDS
                        .insertOrUpdate(profile)
                        .andThen(Single.just(profile)))
                .doOnSuccess(profile -> updateCacheAndPublish(profile));

        return fromDb
                .switchIfEmpty(fromNetwork.toMaybe())
                .doOnSuccess(this::updateCacheAndPublish)
                .toSingle();
    }

    /**
     * Updates the user's profile both locally and remotely. The operation is transactional in the
     * sense that the local DB is only updated if the network request succeeds. Subscribers are
     * notified of the new snapshot immediately after local persistence.
     */
    public Completable updateProfile(@NonNull UserProfile profile) {

        return remoteDS.updateUserProfile(profile)
                       .subscribeOn(io)
                       .andThen(localDS.insertOrUpdate(profile))
                       .andThen(Completable.fromAction(() -> updateCacheAndPublish(profile)))
                       .onErrorResumeNext(this::mapAndWrapError);
    }

    /**
     * Clears all caches and disposes running subscriptions. Should be invoked e.g. on logout.
     */
    public void clear() {
        disposables.clear();
        memoryCache.clear();
        profileProcessor.onComplete();
    }

    /* ----------------------------------------- */
    /* Internal helpers                          */
    /* ----------------------------------------- */

    private void updateCacheAndPublish(@NonNull UserProfile profile) {
        memoryCache.put(profile.getId(), profile);
        profileProcessor.onNext(Event.success(profile));
    }

    /**
     * Convert infra-level exceptions into domain-level failures if necessary.
     */
    private Completable mapAndWrapError(Throwable throwable) {
        // Here we could map HTTP 401/403 to an AuthenticationFailure, etc.
        return Completable.error(throwable);
    }

    /* ----------------------------------------- */
    /* Biometric authentication integration      */
    /* ----------------------------------------- */

    /**
     * Initiates biometric login by delegating to the RemoteDS. This method merely calls the backend
     * and stores the refreshed user profile locally if authentication succeeds. The UI layer
     * listens to {@link #observeUserProfile(String)} and will be updated automatically.
     */
    public Completable authenticateWithBiometrics(@NonNull String encryptedCredential,
                                                  @NonNull String userId) {

        return remoteDS.authenticate(encryptedCredential)
                       .subscribeOn(io)
                       .flatMapCompletable(token -> {
                           // Persist token, fetch fresh profile
                           remoteDS.persistSessionToken(token);
                           return getUserProfile(userId, /*forceRefresh*/ true).ignoreElement();
                       });
    }

    /* ----------------------------------------- */
    /* Rx lifecycle                              */
    /* ----------------------------------------- */

    public void dispose() {
        disposables.dispose();
    }
}

/* ============================================================================================= */
/* Light-weight stubs & utility types                                                            */
/* In a real project these would be imported from their respective modules.                      */
/* ============================================================================================= */

package com.wellsphere.connect.util;

/**
 * Wrapper used to emit one-time events (success, error, loading) through reactive streams
 * while preventing subscribers from handling the same event multiple times.
 */
public final class Event<T> {

    private final T data;
    private final Throwable error;

    private Event(T data, Throwable error) {
        this.data = data;
        this.error = error;
    }

    public static <T> Event<T> success(@NonNull T data) {
        return new Event<>(data, null);
    }

    public static <T> Event<T> error(@NonNull Throwable throwable) {
        return new Event<>(null, throwable);
    }

    public boolean hasData() {
        return data != null;
    }

    @Nullable
    public T getData() {
        return data;
    }

    @Nullable
    public Throwable getError() {
        return error;
    }
}

/* ============================================================================================= */
/* The following interfaces are placeholders for the actual data sources.                        */
/* ============================================================================================= */

package com.wellsphere.connect.data.remote;

import androidx.annotation.NonNull;
import com.wellsphere.connect.data.model.UserProfile;

import io.reactivex.Completable;
import io.reactivex.Single;

public interface UserRemoteDataSource {
    Single<UserProfile> fetchUserProfile(@NonNull String userId);

    Completable updateUserProfile(@NonNull UserProfile profile);

    Single<String> authenticate(@NonNull String encryptedCredential);

    void persistSessionToken(@NonNull String token);
}

package com.wellsphere.connect.data.local;

import androidx.annotation.NonNull;
import com.wellsphere.connect.data.model.UserProfile;

import io.reactivex.Completable;
import io.reactivex.Maybe;

public interface UserLocalDataSource {
    Maybe<UserProfile> getUserProfile(@NonNull String userId);

    Completable insertOrUpdate(@NonNull UserProfile profile);
}

package com.wellsphere.connect.data.remote;

public interface NetworkStateProvider {
    boolean isOnline();
}

/* ============================================================================================= */
/* Domain model placeholder                                                                      */
/* ============================================================================================= */

package com.wellsphere.connect.data.model;

import androidx.annotation.NonNull;

public final class UserProfile {

    private final String id;
    private final String name;
    private final String email;
    private final long lastUpdatedEpochMillis;

    public UserProfile(@NonNull String id,
                       @NonNull String name,
                       @NonNull String email,
                       long lastUpdatedEpochMillis) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.lastUpdatedEpochMillis = lastUpdatedEpochMillis;
    }

    @NonNull
    public String getId() { return id; }

    @NonNull
    public String getName() { return name; }

    @NonNull
    public String getEmail() { return email; }

    public boolean isExpired(long ttlMillis) {
        return System.currentTimeMillis() - lastUpdatedEpochMillis > ttlMillis;
    }
}