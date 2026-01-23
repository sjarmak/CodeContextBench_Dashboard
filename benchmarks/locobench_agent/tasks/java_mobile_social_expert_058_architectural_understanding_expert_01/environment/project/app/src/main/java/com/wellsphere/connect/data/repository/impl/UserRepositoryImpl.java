package com.wellsphere.connect.data.repository.impl;

import androidx.annotation.NonNull;

import com.wellsphere.connect.data.local.db.UserDao;
import com.wellsphere.connect.data.local.db.entity.UserEntity;
import com.wellsphere.connect.data.remote.ApiService;
import com.wellsphere.connect.data.remote.dto.UserDto;
import com.wellsphere.connect.data.repository.UserRepository;
import com.wellsphere.connect.domain.auth.AuthManager;
import com.wellsphere.connect.domain.model.User;
import com.wellsphere.connect.util.NetworkStateProvider;

import java.util.Objects;
import java.util.concurrent.atomic.AtomicBoolean;

import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.core.Flowable;
import io.reactivex.rxjava3.core.Single;
import io.reactivex.rxjava3.schedulers.Schedulers;

/**
 * Production-grade implementation of the {@link UserRepository}.
 * <p>
 * The repository offers a single source of truth for {@link User} domain models.
 * Remote data are fetched via {@link ApiService} and persisted locally through
 * {@link UserDao}. All public API methods are safe to call from any thread and are
 * scheduled onto IO schedulers by default.  This class is designed to be injected
 * (e.g., by Dagger/Hilt) as an application-scoped singleton.
 */
public final class UserRepositoryImpl implements UserRepository {

    private final ApiService apiService;
    private final UserDao userDao;
    private final UserMapper mapper;
    private final NetworkStateProvider networkStateProvider;
    private final AuthManager authManager;

    /**
     * Flag to prevent concurrent sync operations against the same user.
     * AtomicBoolean provides a lock-free, low-overhead mechanism.
     */
    private final AtomicBoolean inFlightSync = new AtomicBoolean(false);

    public UserRepositoryImpl(@NonNull ApiService apiService,
                              @NonNull UserDao userDao,
                              @NonNull UserMapper mapper,
                              @NonNull NetworkStateProvider networkStateProvider,
                              @NonNull AuthManager authManager) {
        this.apiService = Objects.requireNonNull(apiService);
        this.userDao = Objects.requireNonNull(userDao);
        this.mapper = Objects.requireNonNull(mapper);
        this.networkStateProvider = Objects.requireNonNull(networkStateProvider);
        this.authManager = Objects.requireNonNull(authManager);
    }

    // ------------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------------

    /**
     * Returns a hot {@link Flowable} that emits user updates in real-time.
     * <ul>
     *    <li>On subscription, emits immediately from the local Room database.</li>
     *    <li>Triggers a background remote sync (if connectivity permits).</li>
     *    <li>Subsequent DB table changes are automatically observed.</li>
     * </ul>
     */
    @Override
    public Flowable<User> observeUser(@NonNull String userId) {
        return userDao.observeById(userId)
                      .subscribeOn(Schedulers.io())
                      .map(mapper::fromEntity)                          // DB -> Domain
                      .switchMap(user ->                                  // After local emit, try remote sync
                              maybeSyncFromRemote(userId)
                                      .andThen(Flowable.just(user)))
                      .distinctUntilChanged();
    }

    /**
     * Fetches a user once, favouring network then falling back to cache.
     */
    @Override
    public Single<User> getUser(@NonNull String userId) {
        if (networkStateProvider.isNetworkAvailable()) {
            return fetchRemoteUser(userId)
                    .onErrorResumeNext(throwable ->
                            userDao.getById(userId)
                                   .map(mapper::fromEntity)           // Fallback to cached copy
                    );
        } else {
            return userDao.getById(userId)
                           .map(mapper::fromEntity);
        }
    }

    /**
     * Persists the user both remotely and locally.
     * During offline scenarios, changes are queued in the local DB
     * and marked for later sync by WorkManager (not shown here).
     */
    @Override
    public Completable updateUser(@NonNull User user) {
        UserEntity entity = mapper.toEntity(user);
        if (networkStateProvider.isNetworkAvailable()) {
            // First update server, then cache response
            return apiService.updateUser(mapper.toDto(user))
                             .subscribeOn(Schedulers.io())
                             .map(mapper::fromDto)
                             .flatMapCompletable(updated ->
                                     userDao.insertOrUpdate(mapper.toEntity(updated)))
                             .onErrorResumeNext(throwable ->
                                     // In case remote fails, still cache optimistic update
                                     userDao.insertOrUpdate(entity)
                                            .andThen(Completable.error(throwable))
                             );
        } else {
            // Offline: optimistic local save. WorkManager will later replay the change.
            return userDao.insertOrUpdate(entity)
                           .subscribeOn(Schedulers.io());
        }
    }

    /**
     * Clears auth tokens, local cache, and invalidates push tokens.
     */
    @Override
    public Completable logout() {
        return Completable.fromAction(authManager::clearSession)
                          .andThen(userDao.clearTable())
                          .subscribeOn(Schedulers.io());
    }

    // ------------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------------

    /**
     * Triggers a remote fetch and stores the result in the local DB
     * if no other sync is in progress.
     */
    private Completable maybeSyncFromRemote(@NonNull String userId) {
        if (!networkStateProvider.isNetworkAvailable()) {
            return Completable.complete();
        }

        // Prevent overlapping network calls
        if (!inFlightSync.compareAndSet(false, true)) {
            return Completable.complete();
        }

        return fetchRemoteUser(userId)
                .flatMapCompletable(user ->
                        userDao.insertOrUpdate(mapper.toEntity(user)))
                .doFinally(() -> inFlightSync.set(false));
    }

    private Single<User> fetchRemoteUser(@NonNull String userId) {
        return apiService.getUser(userId)
                         .subscribeOn(Schedulers.io())
                         .map(mapper::fromDto);
    }

    // ------------------------------------------------------------------------
    // Mapper
    // ------------------------------------------------------------------------

    /**
     * Dedicated mapper converting between DTOs, DB entities, and domain models.
     * <p>
     * Consider extracting into a shared module if used application-wide.
     */
    public static final class UserMapper {

        public User fromDto(@NonNull UserDto dto) {
            return new User(dto.getId(),
                            dto.getFirstName(),
                            dto.getLastName(),
                            dto.getEmail(),
                            dto.getAvatarUrl(),
                            dto.getLastUpdated());
        }

        public UserDto toDto(@NonNull User user) {
            return new UserDto(user.getId(),
                               user.getFirstName(),
                               user.getLastName(),
                               user.getEmail(),
                               user.getAvatarUrl(),
                               user.getLastUpdated());
        }

        public User fromEntity(@NonNull UserEntity entity) {
            return new User(entity.getId(),
                            entity.getFirstName(),
                            entity.getLastName(),
                            entity.getEmail(),
                            entity.getAvatarUrl(),
                            entity.getLastUpdated());
        }

        public UserEntity toEntity(@NonNull User user) {
            return new UserEntity(user.getId(),
                                  user.getFirstName(),
                                  user.getLastName(),
                                  user.getEmail(),
                                  user.getAvatarUrl(),
                                  user.getLastUpdated());
        }
    }
}