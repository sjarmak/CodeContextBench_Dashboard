package com.wellsphere.connect.data.repository;

import android.annotation.SuppressLint;

import androidx.annotation.NonNull;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;

import com.wellsphere.connect.data.local.dao.PostDao;
import com.wellsphere.connect.data.local.entity.PostEntity;
import com.wellsphere.connect.data.remote.NetworkStateProvider;
import com.wellsphere.connect.data.remote.SocialApiService;
import com.wellsphere.connect.util.Logger;

import java.io.IOException;
import java.util.ArrayDeque;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Queue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

/**
 * SocialRepository encapsulates business-logic for all social-graph interactions.
 *
 * It serves as the single source of truth for {@link PostEntity}s, mediating between the local Room
 * cache and the remote RESTful API.  All I/O work is delegated to an {@link Executor} to keep the
 * main-thread responsive and to comply with strict HIPAA performance guidelines.
 *
 * Thread-safety:  All mutating methods are serialized on a dedicated {@code ioExecutor}.
 */
public final class SocialRepository {

    // region Dependencies
    @NonNull private final SocialApiService apiService;
    @NonNull private final PostDao          postDao;
    @NonNull private final NetworkStateProvider networkStateProvider;
    @NonNull private final Executor         ioExecutor;
    @NonNull private final Logger           logger;
    // endregion

    // Pending outbound requests when the device is offline.
    // In production this would be backed by a more robust queue (e.g., WorkManager + Room).
    private final Queue<Runnable> offlineRequestBuffer = new ArrayDeque<>();

    @SuppressLint("StaticFieldLeak") // safe: Application scoped through DI
    private static volatile SocialRepository INSTANCE;

    /**
     * Returns the singleton instance.  The DI graph normally provides this, but a fallback is
     * supplied for unit test convenience.
     */
    public static SocialRepository getInstance(@NonNull SocialApiService apiService,
                                               @NonNull PostDao postDao,
                                               @NonNull NetworkStateProvider networkStateProvider,
                                               @NonNull Logger logger) {
        if (INSTANCE == null) {
            synchronized (SocialRepository.class) {
                if (INSTANCE == null) {
                    INSTANCE = new SocialRepository(apiService,
                                                    postDao,
                                                    networkStateProvider,
                                                    Executors.newSingleThreadExecutor(),
                                                    logger);
                }
            }
        }
        return INSTANCE;
    }

    // Visible for DI
    public SocialRepository(@NonNull SocialApiService apiService,
                            @NonNull PostDao postDao,
                            @NonNull NetworkStateProvider networkStateProvider,
                            @NonNull Executor ioExecutor,
                            @NonNull Logger logger) {
        this.apiService           = Objects.requireNonNull(apiService);
        this.postDao              = Objects.requireNonNull(postDao);
        this.networkStateProvider = Objects.requireNonNull(networkStateProvider);
        this.ioExecutor           = Objects.requireNonNull(ioExecutor);
        this.logger               = Objects.requireNonNull(logger);
    }

    /**
     * Retrieves the user feed as a reactive {@link LiveData}.  The local cache is emitted first;
     * a network refresh follows when possible.
     *
     * @param userId        The user whose feed should be returned.
     * @param forceRefresh  When true, bypasses cache and fetches from network immediately.
     */
    @NonNull
    public LiveData<Resource<List<PostEntity>>> getFeed(@NonNull String userId,
                                                        boolean forceRefresh) {

        MutableLiveData<Resource<List<PostEntity>>> result = new MutableLiveData<>();
        result.postValue(Resource.loading());

        ioExecutor.execute(() -> {
            try {
                // 1) Read cache
                List<PostEntity> cached = postDao.getFeed(userId);
                if (!cached.isEmpty() && !forceRefresh) {
                    result.postValue(Resource.success(cached));
                }

                // 2) Refresh when network is available or if cache is empty
                if (networkStateProvider.hasInternet()) {
                    List<PostEntity> refreshed = apiService.getFeed(userId);
                    // Persist and emit
                    postDao.replaceFeed(userId, refreshed);
                    result.postValue(Resource.success(refreshed));
                } else if (cached.isEmpty()) {
                    // No cache + no network = error
                    result.postValue(Resource.error(new NetworkUnavailableException()));
                }
            } catch (IOException ioe) {
                logger.e(ioe, "Failed to fetch feed");
                result.postValue(Resource.error(ioe));
            } catch (Exception ex) {
                logger.e(ex, "Unexpected error while fetching feed");
                result.postValue(Resource.error(ex));
            }
        });

        return result;
    }

    /**
     * Creates a new post.  When offline the post is queued and executed automatically once the
     * network becomes available (see {@link #flushOfflineQueue()}).
     */
    @NonNull
    public CompletableFuture<Resource<Void>> createPost(@NonNull PostEntity post) {
        return executeRequest("createPost", () -> apiService.createPost(post),
            () -> postDao.insert(post));
    }

    /**
     * Likes a post.
     */
    @NonNull
    public CompletableFuture<Resource<Void>> likePost(@NonNull String postId) {
        return executeRequest("likePost", () -> apiService.likePost(postId), null);
    }

    /**
     * Attempts to execute all queued operations that were deferred due to connectivity issues.
     * This method is idempotent and safe to call frequently (e.g., from a NetworkCallback).
     */
    public void flushOfflineQueue() {
        if (!networkStateProvider.hasInternet()) return;

        ioExecutor.execute(() -> {
            Runnable action;
            while ((action = offlineRequestBuffer.poll()) != null) {
                try {
                    action.run();
                } catch (Exception ex) {
                    logger.e(ex, "Deferred action failed");
                    // Re-enqueue to retry later
                    offlineRequestBuffer.offer(action);
                    break;
                }
            }
        });
    }

    // region Private helpers ---------------------------------------------------------------------

    /**
     * Wraps synchronous or asynchronous I/O calls into a {@link CompletableFuture} and automatically
     * marshals them onto {@code ioExecutor}.
     */
    private CompletableFuture<Resource<Void>> executeRequest(@NonNull String tag,
                                                             @NonNull IOCall remoteCall,
                                                             Runnable localFallback) {

        CompletableFuture<Resource<Void>> future = new CompletableFuture<>();

        Runnable task = () -> {
            try {
                if (networkStateProvider.hasInternet()) {
                    remoteCall.call();
                    future.complete(Resource.success(null));
                } else {
                    handleOffline(tag, remoteCall, localFallback, future);
                }
            } catch (IOException ioe) {
                logger.e(ioe, "IO error in " + tag);
                future.complete(Resource.error(ioe));
            } catch (Exception ex) {
                logger.e(ex, "Unexpected error in " + tag);
                future.complete(Resource.error(ex));
            }
        };

        ioExecutor.execute(task);
        return future;
    }

    private void handleOffline(@NonNull String tag,
                               @NonNull IOCall remoteCall,
                               Runnable localFallback,
                               CompletableFuture<Resource<Void>> future) {

        logger.w("No internet, buffering " + tag);

        // Execute local fallback (e.g., cache the entity locally)
        Optional.ofNullable(localFallback).ifPresent(Runnable::run);

        // Buffer call for later execution
        offlineRequestBuffer.offer(() -> {
            try {
                remoteCall.call();
            } catch (IOException ioe) {
                // Re-throw; caller will handle by re-queuing.
                throw new RuntimeException(ioe);
            }
        });

        future.complete(Resource.offlineBuffered());
    }

    // endregion

    // region Static helpers ----------------------------------------------------------------------

    private interface IOCall {
        void call() throws IOException;
    }

    /**
     * Standard wrapper to represent loading/success/error states for UI.
     */
    public static final class Resource<T> {
        public enum Status { LOADING, SUCCESS, ERROR, OFFLINE_BUFFERED }

        @NonNull public final Status  status;
        public final T                data;
        public final Throwable        error;

        private Resource(@NonNull Status status, T data, Throwable error) {
            this.status = status;
            this.data   = data;
            this.error  = error;
        }

        public static <T> Resource<T> loading() {
            return new Resource<>(Status.LOADING, null, null);
        }

        public static <T> Resource<T> success(T data) {
            return new Resource<>(Status.SUCCESS, data, null);
        }

        public static <T> Resource<T> error(Throwable error) {
            return new Resource<>(Status.ERROR, null, error);
        }

        public static <T> Resource<T> offlineBuffered() {
            return new Resource<>(Status.OFFLINE_BUFFERED, null, null);
        }
    }

    /**
     * Raised when an operation requires network connectivity but none is available.
     */
    public static final class NetworkUnavailableException extends IOException {
        public NetworkUnavailableException() {
            super("No active network connection");
        }
    }

    // endregion
}