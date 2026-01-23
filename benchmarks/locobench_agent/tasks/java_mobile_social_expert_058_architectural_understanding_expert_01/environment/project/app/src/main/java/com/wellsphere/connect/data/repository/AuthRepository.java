package com.wellsphere.connect.data.repository;

import android.content.Context;
import android.os.SystemClock;

import androidx.annotation.NonNull;
import androidx.annotation.VisibleForTesting;

import com.wellsphere.connect.BuildConfig;
import com.wellsphere.connect.data.local.SecureTokenStore;
import com.wellsphere.connect.data.model.AuthState;
import com.wellsphere.connect.data.model.SessionTokens;
import com.wellsphere.connect.data.model.UserCredentials;
import com.wellsphere.connect.data.model.remote.LoginResponse;
import com.wellsphere.connect.data.remote.AuthRemoteDataSource;
import com.wellsphere.connect.security.BiometricFacade;
import com.wellsphere.connect.util.NetworkUtil;

import java.io.IOException;
import java.util.Objects;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;

import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.core.Observable;
import io.reactivex.rxjava3.core.Single;
import io.reactivex.rxjava3.subjects.BehaviorSubject;
import retrofit2.HttpException;

/**
 * Repository that owns all authentication concerns.
 * It mediates between the remote API and local secure persistence while
 * exposing an observable authentication state to the app.
 *
 * Thread-safety:
 *  • All state-mutating calls are serialized through {@link #ioExecutor}
 *  • {@link BehaviorSubject} guarantees latest emission to late subscribers
 */
public final class AuthRepository {

    //------ Singleton Boilerplate ---------------------------------------------------------------//
    private static volatile AuthRepository INSTANCE;

    public static AuthRepository getInstance(@NonNull Context appCtx,
                                             @NonNull AuthRemoteDataSource remoteDataSource,
                                             @NonNull SecureTokenStore tokenStore,
                                             @NonNull BiometricFacade biometricFacade) {
        if (INSTANCE == null) {
            synchronized (AuthRepository.class) {
                if (INSTANCE == null) {
                    INSTANCE = new AuthRepository(appCtx, remoteDataSource, tokenStore, biometricFacade);
                }
            }
        }
        return INSTANCE;
    }

    //------ Collaborators -----------------------------------------------------------------------//
    private final AuthRemoteDataSource remoteDataSource;
    private final SecureTokenStore tokenStore;
    private final BiometricFacade biometricFacade;
    private final ExecutorService ioExecutor;

    //------ Reactive State ----------------------------------------------------------------------//
    private final BehaviorSubject<AuthState> authStateSubject;

    // Keeps the latest tokens in memory for quick access.
    private final AtomicReference<SessionTokens> cachedTokens = new AtomicReference<>();

    // For token expiry calculation.
    private static final long TOKEN_REFRESH_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes

    //--------------------------------------------------------------------------------------------//
    private AuthRepository(@NonNull Context appCtx,
                           @NonNull AuthRemoteDataSource remoteDataSource,
                           @NonNull SecureTokenStore tokenStore,
                           @NonNull BiometricFacade biometricFacade) {
        this.remoteDataSource = remoteDataSource;
        this.tokenStore       = tokenStore;
        this.biometricFacade  = biometricFacade;
        this.ioExecutor       = Executors.newSingleThreadExecutor(r ->
                new Thread(r, "auth-repo-io"));

        // Hydrate initial state synchronously
        SessionTokens storedTokens = tokenStore.getTokens();
        cachedTokens.set(storedTokens);

        AuthState initial = storedTokens == null ? AuthState.LOGGED_OUT : AuthState.LOGGED_IN;
        this.authStateSubject = BehaviorSubject.createDefault(initial);

        if (BuildConfig.DEBUG) {
            // WARNING: Logging sensitive-ish data. Strip in prod logging pipeline.
            android.util.Log.d("AuthRepository", "Initialized with state=" + initial);
        }
    }

    //============================================================================================//
    // Public API                                                                                 //
    //============================================================================================//

    /**
     * Attempt standard credential-based login.
     */
    public Single<AuthState> login(@NonNull String email, @NonNull String password) {
        return Single.fromCallable(() -> new UserCredentials(email, password))
                .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.io())
                .flatMap(this::performLogin);
    }

    /**
     * Attempt biometric-protected login. Caller must guarantee
     * that device credentials have already been verified at UI layer.
     */
    public Single<AuthState> biometricLogin() {
        return biometricFacade
                .decryptCredentials()
                .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.io())
                .flatMap(this::performLogin);
    }

    /**
     * Emits the current authentication state and any subsequent changes.
     */
    public Observable<AuthState> getAuthStateStream() {
        return authStateSubject.hide().distinctUntilChanged();
    }

    /**
     * Force logout – clears tokens and pushes LOGGED_OUT state.
     */
    public Completable logout() {
        return Completable.fromAction(() -> {
            tokenStore.clear();
            cachedTokens.set(null);
            pushState(AuthState.LOGGED_OUT);
        }).subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.io());
    }

    /**
     * Refresh the access token if it's about to expire.
     * Safe to call frequently; no-op when refresh not needed.
     */
    public Completable ensureFreshToken() {
        return Completable.fromRunnable(() -> {
            SessionTokens tokens = cachedTokens.get();
            if (tokens == null) {
                return; // Not logged in.
            }

            long timeLeft = tokens.getExpiresAtEpochMillis() - System.currentTimeMillis();
            if (timeLeft > TOKEN_REFRESH_THRESHOLD_MS) return; // Still valid.

            // Network check early-exit to avoid blocking call.
            if (!NetworkUtil.isOnline()) {
                throw new IOException("No internet available for token refresh");
            }

            // Do refresh.
            SessionTokens refreshed = remoteDataSource
                    .refreshToken(tokens.getRefreshToken())
                    .blockingGet();

            persistAndCacheTokens(refreshed);
            pushState(AuthState.LOGGED_IN);
        }).subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.io());
    }

    /**
     * Synchronously fetch a valid bearer token for networking layer.
     * If token is expiring soon, performs a blocking refresh.
     * Should be called off the UI thread.
     */
    public @NonNull String blockingGetValidAccessToken() throws IOException {
        SessionTokens current = cachedTokens.get();

        if (current == null) throw new IllegalStateException("User not authenticated");

        long timeLeft = current.getExpiresAtEpochMillis() - System.currentTimeMillis();
        if (timeLeft < TOKEN_REFRESH_THRESHOLD_MS) {
            // Blocking path: refresh token
            try {
                SessionTokens refreshed = remoteDataSource
                        .refreshToken(current.getRefreshToken())
                        .blockingGet();
                persistAndCacheTokens(refreshed);
                current = refreshed;
            } catch (Exception e) {
                throw unwrap(e);
            }
        }
        return current.getAccessToken();
    }

    //============================================================================================//
    // Internal helpers                                                                           //
    //============================================================================================//

    private Single<AuthState> performLogin(@NonNull UserCredentials creds) {
        return remoteDataSource
                .login(creds)
                .map(this::handleLoginSuccess)
                .doOnError(err -> {
                    if (BuildConfig.DEBUG) android.util.Log.w("AuthRepository", "Login failed", err);
                });
    }

    private AuthState handleLoginSuccess(@NonNull LoginResponse response) throws IOException {
        // Persist tokens atomically
        persistAndCacheTokens(response.getTokens());

        // Persist credentials for biometric re-logic only when user enables it
        if (response.isBiometricOptIn()) {
            biometricFacade.encryptAndStoreCredentials(
                    new UserCredentials(response.getEmail(), response.getEchoPassword()));
        }

        pushState(AuthState.LOGGED_IN);

        return AuthState.LOGGED_IN;
    }

    private void pushState(@NonNull AuthState newState) {
        authStateSubject.onNext(newState);
    }

    private void persistAndCacheTokens(@NonNull SessionTokens tokens) throws IOException {
        tokenStore.save(tokens);
        cachedTokens.set(tokens);
    }

    private static IOException unwrap(Throwable throwable) {
        if (throwable instanceof IOException) return (IOException) throwable;
        if (throwable instanceof HttpException) return new IOException(((HttpException) throwable).message(), throwable);
        return new IOException("Unexpected auth error", throwable);
    }

    //============================================================================================//
    // Testing helpers                                                                            //
    //============================================================================================//

    @VisibleForTesting
    void clearForTesting() {
        tokenStore.clear();
        cachedTokens.set(null);
        pushState(AuthState.LOGGED_OUT);
    }
}