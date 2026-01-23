package com.wellsphere.connect.data.repository.impl;

import android.annotation.SuppressLint;

import androidx.annotation.NonNull;
import androidx.annotation.VisibleForTesting;
import androidx.lifecycle.LiveData;

import com.wellsphere.connect.data.local.dao.JournalDao;
import com.wellsphere.connect.data.local.entity.JournalEntryEntity;
import com.wellsphere.connect.data.remote.api.JournalApi;
import com.wellsphere.connect.data.remote.dto.JournalEntryDto;
import com.wellsphere.connect.data.repository.JournalRepository;
import com.wellsphere.connect.di.AppExecutors;
import com.wellsphere.connect.util.NetworkMonitor;

import java.io.IOException;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.core.Flowable;
import io.reactivex.rxjava3.core.Single;
import io.reactivex.rxjava3.processors.BehaviorProcessor;
import io.reactivex.rxjava3.schedulers.Schedulers;
import retrofit2.HttpException;
import timber.log.Timber;

/**
 * JournalRepositoryImpl is the single source of truth for all journal-entry-related data.
 * <p>
 *     Responsibilities:
 *     • Expose a reactive stream of {@link JournalEntryEntity} objects to the ViewModel layer.<br/>
 *     • Orchestrate local caching (Room) and remote persistence (REST, Retrofit).<br/>
 *     • Handle offline-first behavior and optimistic updates.<br/>
 *     • Guarantee at-least-once delivery to the backend, with exponential back-off retries.<br/>
 * </p>
 *
 * This implementation is thread-safe and lifecycle-aware, leveraging RxJava3,
 * {@link AppExecutors} and {@link NetworkMonitor}.
 */
@SuppressLint("CheckResult")
public final class JournalRepositoryImpl implements JournalRepository {

    // region – Constants
    private static final int REMOTE_PAGE_SIZE = 50;
    private static final int MAX_RETRY_COUNT = 3;
    private static final long RETRY_BACKOFF_MILLIS = TimeUnit.SECONDS.toMillis(5);
    // endregion

    // region – Member variables
    private final JournalDao journalDao;
    private final JournalApi journalApi;
    private final NetworkMonitor networkMonitor;
    private final AppExecutors appExecutors;

    /**
     * Processor that emits whenever a manual refresh is triggered.  ViewModels can subscribe
     * via {@link #getJournalEntries(String)} and always receive the latest data.
     */
    private final BehaviorProcessor<String> manualRefreshProcessor = BehaviorProcessor.create();
    // endregion

    // region – Constructor
    public JournalRepositoryImpl(@NonNull JournalDao journalDao,
                                 @NonNull JournalApi journalApi,
                                 @NonNull NetworkMonitor networkMonitor,
                                 @NonNull AppExecutors appExecutors) {
        this.journalDao = journalDao;
        this.journalApi = journalApi;
        this.networkMonitor = networkMonitor;
        this.appExecutors = appExecutors;
    }
    // endregion

    // region – Repository API

    /**
     * Stream of journal entries for the specified user.  The stream combines:
     *  (1) Local Room DB contents      – emitted immediately for snappy UI.
     *  (2) Remote fetch on subscription – populates/updates local cache.
     *  (3) Manual refreshes signaled via {@link #refresh(String)}.
     */
    @Override
    public Flowable<List<JournalEntryEntity>> getJournalEntries(@NonNull String userId) {
        return Flowable.merge(
                // Initial local DB subscription
                journalDao.observeByUser(userId)
                           .subscribeOn(Schedulers.io()),
                // Manual refreshes
                manualRefreshProcessor
                        .filter(id -> id.equals(userId))
                        .flatMapSingle(ignore -> pullLatestFromBackend(userId))
                        .flatMap(ignore -> journalDao.observeByUser(userId))
                        .subscribeOn(Schedulers.io())
        ).distinctUntilChanged();
    }

    /**
     * Create/Update a journal entry locally and attempt to sync with backend.
     * Returns a Completable that completes once local persistence is done.
     */
    @Override
    public Completable upsertEntry(@NonNull JournalEntryEntity entity) {
        JournalEntryEntity toSave = entity;
        if (toSave.getId() == null) {
            // Generate local UUID if the entry is new.
            toSave = entity.toBuilder()
                           .setId(UUID.randomUUID().toString())
                           .setPendingSync(true)
                           .build();
        } else {
            toSave = toSave.toBuilder().setPendingSync(true).build();
        }

        return Completable.fromAction(() -> journalDao.upsert(toSave))
                          .subscribeOn(Schedulers.io())
                          .andThen(trySyncPendingEntries()); // Fire-and-forget remote sync
    }

    /**
     * Deletes a journal entry both locally and remotely.
     */
    @Override
    public Completable deleteEntry(@NonNull JournalEntryEntity entity) {
        return Completable.fromAction(() -> journalDao.delete(entity))
                          .subscribeOn(Schedulers.io())
                          .andThen(networkMonitor.isConnectedSingle()
                                .flatMapCompletable(isConnected -> {
                                    if (!isConnected || entity.getId() == null) {
                                        return Completable.complete();
                                    }
                                    return journalApi.deleteEntry(entity.getId())
                                                     .subscribeOn(Schedulers.io())
                                                     .retryWhen(errors -> errors
                                                             .zipWith(Flowable.range(1, MAX_RETRY_COUNT), (err, count) -> count)
                                                             .flatMap(retryCount -> {
                                                                 Timber.w("Retrying delete #%d", retryCount);
                                                                 return Flowable.timer(retryCount * RETRY_BACKOFF_MILLIS, TimeUnit.MILLISECONDS);
                                                             })
                                                     )
                                                     .onErrorComplete(throwable -> {
                                                         Timber.e(throwable, "Failed to delete remote entry %s – will retry later.", entity.getId());
                                                         // Mark as "tombstone" so that a background sync can retry.
                                                         JournalEntryEntity tombstone = entity.toBuilder()
                                                                                              .setPendingDeletion(true)
                                                                                              .build();
                                                         journalDao.upsert(tombstone);
                                                         return true; // Swallow error
                                                     });
                                }));
    }

    /**
     * Explicitly refreshes data from the backend and stores the latest snapshot in DB.
     */
    @Override
    public Completable refresh(@NonNull String userId) {
        manualRefreshProcessor.onNext(userId);
        return Completable.complete();
    }
    // endregion

    // region – Background synchronisation

    /**
     * Periodically invoked by WorkManager (or app foreground) to push any locally pending changes.
     */
    @Override
    public Completable trySyncPendingEntries() {
        return networkMonitor.isConnectedSingle()
                .flatMapCompletable(isOnline -> {
                    if (!isOnline) {
                        return Completable.complete();
                    }
                    return journalDao.getPendingSync()
                            .flatMapCompletable(pendingList -> {
                                if (pendingList.isEmpty()) {
                                    return Completable.complete();
                                }
                                return journalApi.upsertEntries(JournalEntryDto.fromEntities(pendingList))
                                                 .map(JournalEntryDto::toEntities)
                                                 .flatMapCompletable(serverEntities -> Completable.fromAction(() -> {
                                                     // Mark as synced
                                                     for (JournalEntryEntity entity : pendingList) {
                                                         entity = entity.toBuilder().setPendingSync(false).build();
                                                         journalDao.upsert(entity);
                                                     }
                                                     // Merge server authoritative state
                                                     journalDao.upsertAll(serverEntities);
                                                 }))
                                                 .subscribeOn(Schedulers.io())
                                                 .retryWhen(buildRetryStrategy("syncPending"));
                            });
                })
                .subscribeOn(Schedulers.io());
    }
    // endregion

    // region – Private helpers

    /**
     * Retrieves the full remote list (paged) and updates the local cache.
     */
    private Single<Boolean> pullLatestFromBackend(@NonNull String userId) {
        return networkMonitor.isConnectedSingle()
                .flatMap(isOnline -> {
                    if (!isOnline) {
                        Timber.d("Skipping pullLatest – offline");
                        return Single.just(false);
                    }

                    return fetchPaged(userId, 1)
                            .retryWhen(buildRetryStrategy("fetchPaged"))
                            .map(serverEntities -> {
                                appExecutors.diskIO().execute(() -> {
                                    // Replace cache transactionally
                                    journalDao.replaceForUser(userId, serverEntities);
                                });
                                return true;
                            });
                })
                .subscribeOn(Schedulers.io());
    }

    /**
     * Fetches all pages recursively.
     */
    private Single<List<JournalEntryEntity>> fetchPaged(String userId, int page) {
        return journalApi.getEntries(userId, page, REMOTE_PAGE_SIZE)
                         .map(JournalEntryDto::toEntities)
                         .flatMap(list -> {
                             if (list.size() < REMOTE_PAGE_SIZE) {
                                 return Single.just(list); // Last page
                             }
                             return fetchPaged(userId, page + 1)
                                     .map(next -> {
                                         list.addAll(next);
                                         return list;
                                     });
                         })
                         .subscribeOn(Schedulers.io());
    }

    /**
     * Builds an exponential back-off retry strategy for network operations.
     */
    private Flowable<Long> buildRetryStrategy(@NonNull String tag) {
        return errors -> errors
                .zipWith(Flowable.range(1, MAX_RETRY_COUNT), (throwable, retryCount) -> {
                    if (retryCount == MAX_RETRY_COUNT) {
                        throw new RuntimeException(throwable);
                    }
                    return retryCount;
                })
                .flatMap(retryCount -> {
                    long delay = (long) Math.pow(2, retryCount) * RETRY_BACKOFF_MILLIS;
                    Timber.w("%s – retry #%d in %d ms", tag, retryCount, delay);
                    return Flowable.timer(delay, TimeUnit.MILLISECONDS);
                });
    }
    // endregion

    // region – Testing helpers
    @VisibleForTesting
    BehaviorProcessor<String> getManualRefreshProcessor() {
        return manualRefreshProcessor;
    }
    // endregion
}