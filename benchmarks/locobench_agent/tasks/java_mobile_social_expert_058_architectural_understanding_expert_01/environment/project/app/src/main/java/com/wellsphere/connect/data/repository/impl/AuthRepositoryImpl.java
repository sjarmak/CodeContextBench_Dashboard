package com.wellsphere.connect.data.repository.impl;

import android.annotation.SuppressLint;
import android.content.Context;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;

import com.wellsphere.connect.data.local.AuthDao;
import com.wellsphere.connect.data.local.model.AuthEntity;
import com.wellsphere.connect.data.model.User;
import com.wellsphere.connect.data.model.request.LoginRequest;
import com.wellsphere.connect.data.model.request.RefreshRequest;
import com.wellsphere.connect.data.model.request.RegisterRequest;
import com.wellsphere.connect.data.model.response.AuthResponse;
import com.wellsphere.connect.data.network.AuthApiService;
import com.wellsphere.connect.data.repository.contract.AuthRepository;
import com.wellsphere.connect.security.BiometricAuthenticator;
import com.wellsphere.connect.security.TokenManager;
import com.wellsphere.connect.util.NetworkStatusProvider;

import java.io.IOException;
import java.util.concurrent.atomic.AtomicBoolean;

import io.reactivex.Completable;
import io.reactivex.Observable;
import io.reactivex.Single;
import io.reactivex.schedulers.Schedulers;
import retrofit2.HttpException;
import retrofit2.Response;

/**
 * Production-grade implementation of the {@link AuthRepository}.
 * <p>
 * Responsibilities:
 * <ul>
 *     <li>Delegate authentication calls to {@link AuthApiService}</li>
 *     <li>Persist and cache token information via {@link TokenManager}</li>
 *     <li>Cache the current {@link User} in a {@link AuthDao} Room database</li>
 *     <li>Provide a reactive, lifecycle-aware authentication state ({@link #authState})</li>
 *     <li>Fallback to offline / biometric auth when network is unavailable</li>
 * </ul>
 *
 * Threading policy: All IO-bound work runs on {@link Schedulers#io()}.
 */
public class AuthRepositoryImpl implements AuthRepository {

    private static final String TAG = "AuthRepository";

    private final AuthApiService apiService;
    private final AuthDao authDao;
    private final TokenManager tokenManager;
    private final NetworkStatusProvider networkStatusProvider;
    private final BiometricAuthenticator biometricAuthenticator;

    /** In-memory copy of authentication state */
    private final MutableLiveData<Boolean> authState = new MutableLiveData<>(false);

    /** Guards multiple simultaneous refresh() calls */
    private final AtomicBoolean isRefreshing = new AtomicBoolean(false);

    @SuppressLint("CheckResult")
    public AuthRepositoryImpl(@NonNull Context appContext,
                              @NonNull AuthApiService apiService,
                              @NonNull AuthDao authDao,
                              @NonNull TokenManager tokenManager,
                              @NonNull NetworkStatusProvider networkStatusProvider,
                              @NonNull BiometricAuthenticator biometricAuthenticator) {

        this.apiService = apiService;
        this.authDao = authDao;
        this.tokenManager = tokenManager;
        this.networkStatusProvider = networkStatusProvider;
        this.biometricAuthenticator = biometricAuthenticator;

        // Observe token changes & update auth state accordingly
        tokenManager.observeToken()
                .subscribeOn(Schedulers.io())
                .subscribe(token -> authState.postValue(token != null && !token.isExpired()),
                        throwable -> Log.e(TAG, "observeToken() error", throwable));
    }

    /* *********************************************************************************************
     * Public API
     * *********************************************************************************************/

    @Override
    public LiveData<Boolean> isLoggedIn() {
        return authState;
    }

    @Override
    public Single<User> login(@NonNull String email, @NonNull String password) {
        return networkStatusProvider.requireConnection()
                .andThen(apiService.login(new LoginRequest(email.trim(), password)))
                .subscribeOn(Schedulers.io())
                .flatMap(this::handleAuthResponse)
                .doOnError(throwable -> Log.e(TAG, "login() failed", throwable));
    }

    @Override
    public Single<User> register(@NonNull RegisterRequest registerRequest) {
        return networkStatusProvider.requireConnection()
                .andThen(apiService.register(registerRequest))
                .subscribeOn(Schedulers.io())
                .flatMap(this::handleAuthResponse)
                .doOnError(throwable -> Log.e(TAG, "register() failed", throwable));
    }

    @Override
    public Completable logout() {
        return Completable.fromAction(() -> {
            tokenManager.clear();
            authDao.clear();
            authState.postValue(false);
        }).subscribeOn(Schedulers.io());
    }

    @Override
    public Single<String> refreshToken() {
        if (isRefreshing.getAndSet(true)) {
            // Another refresh() is already in progress – avoid duplication
            return tokenManager.getRawToken().firstOrError()
                    .doFinally(() -> isRefreshing.set(false));
        }

        return tokenManager.getRefreshToken().firstOrError()
                .flatMap(refresh -> {
                    if (refresh == null) {
                        throw new IllegalStateException("Refresh token is missing");
                    }
                    return apiService.refreshToken(new RefreshRequest(refresh));
                })
                .subscribeOn(Schedulers.io())
                .flatMap(this::handleRefreshResponse)
                .doFinally(() -> isRefreshing.set(false))
                .doOnError(t -> Log.e(TAG, "refreshToken() failed", t));
    }

    @Override
    public Single<User> biometricLogin() {
        return biometricAuthenticator.authenticate()
                .subscribeOn(Schedulers.io())
                .flatMap(ignored ->
                        authDao.getCurrentUser()
                                .switchIfEmpty(Single.error(
                                        new IllegalStateException("No cached user for biometric login")))
                                .flatMap(user -> {
                                    String storedToken = tokenManager.peekRawToken();
                                    if (storedToken == null) {
                                        return Single.error(
                                                new IllegalStateException("Token missing for biometric login"));
                                    }
                                    authState.postValue(true);
                                    return Single.just(user);
                                })
                );
    }

    /* *********************************************************************************************
     * Internal helpers
     * *********************************************************************************************/

    /**
     * Store tokens + user in local cache, update LiveData, and return a {@link User}.
     */
    private Single<User> handleAuthResponse(Response<AuthResponse> response) {
        if (!response.isSuccessful() || response.body() == null) {
            return Single.error(parseHttpError(response));
        }

        AuthResponse body = response.body();
        return persistUserAndTokens(body)
                .toSingle(() -> body.getUser());
    }

    private Single<String> handleRefreshResponse(Response<AuthResponse> response) {
        if (!response.isSuccessful() || response.body() == null) {
            return Single.error(parseHttpError(response));
        }
        AuthResponse body = response.body();
        return persistUserAndTokens(body)
                .toSingle(() -> body.getAccessToken());
    }

    private Completable persistUserAndTokens(AuthResponse body) {
        return Completable.fromAction(() -> {
            tokenManager.saveTokens(body.getAccessToken(),
                    body.getRefreshToken(),
                    body.getExpiresIn());

            AuthEntity entity = AuthEntity.from(body.getUser());
            authDao.insertOrReplace(entity);
            authState.postValue(true);
        }).subscribeOn(Schedulers.io());
    }

    private Throwable parseHttpError(Response<?> response) {
        try {
            return new HttpException(response);
        } catch (Exception ignored) {
            return new IOException("Network call failed with code: " + response.code());
        }
    }

    /* *********************************************************************************************
     * DEBUG / TEST HELPERS
     * *********************************************************************************************/

    /**
     * Force-sets the current user (used ONLY in end-to-end tests).
     */
    @SuppressWarnings("unused")
    public Completable debugSetUser(User user, String accessToken) {
        return Completable.fromAction(() -> {
            tokenManager.saveTokens(accessToken, "debug-refresh", 3600);
            authDao.insertOrReplace(AuthEntity.from(user));
            authState.postValue(true);
        }).subscribeOn(Schedulers.io());
    }
}