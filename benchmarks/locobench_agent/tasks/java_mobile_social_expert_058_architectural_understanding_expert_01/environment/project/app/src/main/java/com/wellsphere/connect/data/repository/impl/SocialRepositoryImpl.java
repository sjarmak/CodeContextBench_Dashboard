package com.wellsphere.connect.data.repository.impl;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.wellsphere.connect.data.datasource.local.SocialLocalDataSource;
import com.wellsphere.connect.data.datasource.remote.SocialRemoteDataSource;
import com.wellsphere.connect.data.mapper.PostMapper;
import com.wellsphere.connect.data.model.PagedResult;
import com.wellsphere.connect.data.model.PagingParams;
import com.wellsphere.connect.data.model.local.PostEntity;
import com.wellsphere.connect.domain.model.Post;
import com.wellsphere.connect.domain.repository.SocialRepository;
import com.wellsphere.connect.util.NetworkUtil;
import com.wellsphere.connect.util.logging.AppLogger;

import java.io.IOException;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.core.Flowable;
import io.reactivex.rxjava3.core.Single;
import retrofit2.HttpException;

/**
 * Production-grade implementation of {@link SocialRepository}.
 *
 * <p>This class orchestrates social-feed operations across local and remote data-sources,
 * transparently handling connectivity loss, conflict-free merges, and incremental paging.</p>
 *
 * <p>Threading model:
 * <ul>
 *     <li>Local DB operations execute on a dedicated disk I/O executor.</li>
 *     <li>Network operations execute on RxJava's IO scheduler.</li>
 *     <li>Mappers run on the calling thread for minimal overhead.</li>
 * </ul></p>
 */
@SuppressWarnings("Convert2Lambda")
public final class SocialRepositoryImpl implements SocialRepository {

    private static final int DEFAULT_PAGE_SIZE = 20;

    private final SocialRemoteDataSource remoteDataSource;
    private final SocialLocalDataSource  localDataSource;
    private final PostMapper             postMapper;
    private final Executor               diskExecutor;

    public SocialRepositoryImpl(@NonNull SocialRemoteDataSource remoteDataSource,
                                @NonNull SocialLocalDataSource localDataSource,
                                @NonNull PostMapper postMapper) {
        this.remoteDataSource = remoteDataSource;
        this.localDataSource  = localDataSource;
        this.postMapper       = postMapper;
        this.diskExecutor     = Executors.newSingleThreadExecutor();
    }

    // -------------------------------------------
    // Feed
    // -------------------------------------------

    /**
     * Returns a reactive stream of {@link Post}s for the given page configuration.
     * The stream emits cached data first and refreshes when network data becomes available.
     */
    @Override
    public Flowable<PagedResult<Post>> getFeed(@NonNull final PagingParams pagingParams) {

        final PagingParams safeParams = (pagingParams == null)
                ? new PagingParams(0, DEFAULT_PAGE_SIZE)
                : pagingParams.coercePageSize(DEFAULT_PAGE_SIZE);

        // 1) Load from cache.
        Flowable<PagedResult<Post>> cacheFlowable = localDataSource
                .getPosts(safeParams)
                .map(result -> result.map(postMapper::mapFromEntity));

        // 2) Fetch remote page & cache it.
        Single<PagedResult<Post>> remoteSingle = fetchAndCacheRemotePage(safeParams);

        // 3) Concatenate cache (immediate) + remote (once available).
        return cacheFlowable.concatWith(remoteSingle.toFlowable());
    }

    /**
     * Fetches a page from the remote API and persists it atomically.
     */
    private Single<PagedResult<Post>> fetchAndCacheRemotePage(@NonNull final PagingParams params) {

        return remoteDataSource
                .getFeed(params)
                .flatMap(apiResult -> {
                    // Persist on dedicated disk thread.
                    return Single.fromCallable(() -> {
                        localDataSource.transaction(new Runnable() {
                            @Override public void run() {
                                List<PostEntity> toInsert = postMapper.mapToEntityList(apiResult.getItems());
                                localDataSource.insertOrUpdatePosts(toInsert);
                            }
                        }, diskExecutor);

                        return apiResult.map(postMapper::map);
                    });
                })
                .onErrorResumeNext(throwable -> {
                    // Emit whatever cached data we have if network fails.
                    AppLogger.e(throwable, "Failed to fetch remote feed page");
                    return localDataSource
                            .getPosts(params)
                            .first(new PagedResult<>(Collections.<PostEntity>emptyList(), false, params))
                            .map(result -> result.map(postMapper::mapFromEntity));
                });
    }

    // -------------------------------------------
    // Post creation
    // -------------------------------------------

    @Override
    public Completable createPost(@NonNull final Post post) {
        final PostEntity entity = postMapper.mapToEntity(post);

        // Optimistically insert into the cache for immediate UI feedback.
        Completable cacheWrite = Completable
                .fromAction(() -> localDataSource.upsertPost(entity))
                .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.from(diskExecutor));

        // Attempt network push if online, else mark pending sync.
        Completable networkWrite = Completable.defer(() -> {
            if (NetworkUtil.isOnline()) {
                return remoteDataSource
                        .createPost(post)
                        .flatMapCompletable(serverPost -> {
                            // Update local record with server-assigned IDs / timestamps.
                            PostEntity updated = postMapper.mapToEntity(serverPost);
                            return Completable.fromAction(() ->
                                    localDataSource.upsertPost(updated))
                                    .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.from(diskExecutor));
                        });
            } else {
                // Flag row as pending for later sync.
                return Completable.fromAction(() ->
                        localDataSource.markPendingUpload(entity.getLocalId()))
                        .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.from(diskExecutor));
            }
        });

        return cacheWrite.andThen(networkWrite);
    }

    // -------------------------------------------
    // Like / Unlike
    // -------------------------------------------

    @Override
    public Completable toggleLike(@NonNull final String postId, final boolean like) {

        Completable localToggle = Completable.fromAction(() ->
                localDataSource.toggleLike(postId, like))
                .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.from(diskExecutor));

        Completable remoteToggle = Completable.defer(() -> {
            if (!NetworkUtil.isOnline()) {
                return Completable.fromAction(() ->
                        localDataSource.markPendingLike(postId, like))
                        .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.from(diskExecutor));
            }
            return (like ? remoteDataSource.likePost(postId) : remoteDataSource.unlikePost(postId))
                    .onErrorResumeNext(throwable -> {
                        // Rollback local like state on unrecoverable HTTP errors (≠ network).
                        if (throwable instanceof HttpException) {
                            return Completable.fromAction(() ->
                                    localDataSource.toggleLike(postId, !like))
                                    .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.from(diskExecutor))
                                    .andThen(Completable.error(throwable));
                        }
                        // For IO issues, keep optimistic state & defer sync.
                        return Completable.fromAction(() ->
                                localDataSource.markPendingLike(postId, like))
                                .subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.from(diskExecutor));
                    });
        });

        return localToggle.andThen(remoteToggle);
    }

    // -------------------------------------------
    // Offline-first synchronisation
    // -------------------------------------------

    /**
     * Pushes all locally pending social actions (post creations, likes, etc.) to the backend.
     * Invoked by SyncWorker or when connectivity is restored.
     */
    @Override
    public Completable syncPendingActions() {

        return Completable.fromRunnable(() -> {

            if (!NetworkUtil.isOnline()) {
                AppLogger.i("Skip sync: offline");
                return;
            }

            List<PostEntity> pendingPosts = localDataSource.getPendingPosts();
            for (PostEntity entity : pendingPosts) {
                try {
                    Post   domain  = postMapper.mapFromEntity(entity);
                    Post   created = remoteDataSource.createPost(domain).blockingGet();
                    PostEntity synced = postMapper.mapToEntity(created);
                    localDataSource.upsertPost(synced);
                } catch (IOException | HttpException ex) {
                    AppLogger.e(ex, "Post sync failed for id=%s", entity.getLocalId());
                    // Keep item pending for next cycle.
                }
            }

            // Sync likes
            List<SocialLocalDataSource.PendingLike> pendingLikes = localDataSource.getPendingLikes();
            for (SocialLocalDataSource.PendingLike p : pendingLikes) {
                try {
                    if (p.isLike()) {
                        remoteDataSource.likePost(p.getPostId()).blockingAwait();
                    } else {
                        remoteDataSource.unlikePost(p.getPostId()).blockingAwait();
                    }
                    localDataSource.clearPendingLike(p.getPostId());
                } catch (IOException | HttpException ex) {
                    AppLogger.e(ex, "Like sync failed for postId=%s", p.getPostId());
                    // Remain pending.
                }
            }

        }).subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.io());
    }

    // -------------------------------------------
    // Maintenance
    // -------------------------------------------

    @Override
    public Completable clearAll() {
        return Completable.fromRunnable(() -> {
            localDataSource.clearAll();
        }).subscribeOn(io.reactivex.rxjava3.schedulers.Schedulers.from(diskExecutor));
    }
}