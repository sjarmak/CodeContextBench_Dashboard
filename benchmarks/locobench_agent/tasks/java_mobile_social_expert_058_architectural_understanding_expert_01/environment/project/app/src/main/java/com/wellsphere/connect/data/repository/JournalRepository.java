package com.wellsphere.connect.data.repository;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.annotation.WorkerThread;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MediatorLiveData;
import androidx.lifecycle.MutableLiveData;

import com.wellsphere.connect.data.local.dao.JournalDao;
import com.wellsphere.connect.data.local.entity.JournalEntryEntity;
import com.wellsphere.connect.data.mapper.JournalMapper;
import com.wellsphere.connect.data.remote.api.JournalApiService;
import com.wellsphere.connect.data.remote.model.JournalEntryDto;
import com.wellsphere.connect.util.AppExecutors;
import com.wellsphere.connect.util.ConnectivityChecker;
import com.wellsphere.connect.util.Logger;
import com.wellsphere.connect.util.Resource;
import com.wellsphere.connect.util.Status;

import java.io.IOException;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import retrofit2.Response;

/**
 * Repository that handles Journal related data operations.
 *
 * Combines access to the local Room database with calls to the remote REST API, exposing
 * a clean API for the ViewModel layer while encapsulating caching, offline-first strategy
 * and sync conflict resolution.
 *
 * The implementation follows Google’s recommended “Network Bound Resource” pattern.
 */
@SuppressWarnings({"unused", "WeakerAccess"})
public class JournalRepository {

    private static final String TAG = "JournalRepository";

    private static final long SYNC_COOLDOWN_WINDOW_MS = TimeUnit.MINUTES.toMillis(5);

    @Nullable
    private static volatile JournalRepository INSTANCE;

    private final JournalDao journalDao;
    private final JournalApiService apiService;
    private final JournalMapper mapper;
    private final ConnectivityChecker connectivityChecker;
    private final AppExecutors executors;

    /* Timestamp of the last full sync to avoid hammering backend while user scrolls */
    private long lastSyncTimestampMs = 0;

    private JournalRepository(@NonNull JournalDao journalDao,
                              @NonNull JournalApiService apiService,
                              @NonNull JournalMapper mapper,
                              @NonNull ConnectivityChecker connectivityChecker,
                              @NonNull AppExecutors executors) {
        this.journalDao = journalDao;
        this.apiService = apiService;
        this.mapper = mapper;
        this.connectivityChecker = connectivityChecker;
        this.executors = executors;
    }

    /* Singleton accessor */
    public static JournalRepository getInstance(@NonNull JournalDao journalDao,
                                                @NonNull JournalApiService apiService,
                                                @NonNull JournalMapper mapper,
                                                @NonNull ConnectivityChecker connectivityChecker,
                                                @NonNull AppExecutors executors) {
        if (INSTANCE == null) {
            synchronized (JournalRepository.class) {
                if (INSTANCE == null) {
                    INSTANCE = new JournalRepository(journalDao, apiService, mapper, connectivityChecker, executors);
                }
            }
        }
        return Objects.requireNonNull(INSTANCE);
    }

    // -----------------------------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------------------------

    /**
     * Returns a reactive stream of the current user’s journal entries.
     * If forceRefresh is requested and network is available a remote call will be performed.
     */
    public LiveData<Resource<List<JournalEntryEntity>>> getJournalEntries(@NonNull final String userId,
                                                                          final boolean forceRefresh) {

        final MediatorLiveData<Resource<List<JournalEntryEntity>>> result = new MediatorLiveData<>();
        result.postValue(Resource.loading(null));

        LiveData<List<JournalEntryEntity>> dbSource = journalDao.getAllForUser(userId);

        result.addSource(dbSource, entities -> result.setValue(Resource.success(entities)));

        boolean shouldFetch =
                forceRefresh ||
                (System.currentTimeMillis() - lastSyncTimestampMs) > SYNC_COOLDOWN_WINDOW_MS;

        if (shouldFetch && connectivityChecker.isConnected()) {
            executors.networkIO().execute(() -> {
                try {
                    Response<List<JournalEntryDto>> response = apiService.getAllEntries(userId).execute();
                    if (response.isSuccessful() && response.body() != null) {
                        List<JournalEntryEntity> remoteEntities = mapper.toEntity(response.body());

                        // Update local cache
                        journalDao.replaceAllForUser(userId, remoteEntities);
                        lastSyncTimestampMs = System.currentTimeMillis();
                    } else {
                        Logger.w(TAG, "getJournalEntries() remote call failed: " + response.code());
                        result.postValue(Resource.error("Server error " + response.code(), null));
                    }
                } catch (IOException e) {
                    Logger.e(TAG, "getJournalEntries() network IO exception", e);
                    result.postValue(Resource.error("Network error: " + e.getMessage(), null));
                }
            });
        }

        return result;
    }

    /**
     * Retrieves a single journal entry by id from the local cache. If the item is missing locally
     * and connectivity exists, fetch it from server and cache.
     */
    public LiveData<Resource<JournalEntryEntity>> getJournalEntryById(@NonNull final String entryId,
                                                                      @NonNull final String userId) {

        final MediatorLiveData<Resource<JournalEntryEntity>> result = new MediatorLiveData<>();
        result.postValue(Resource.loading(null));

        LiveData<JournalEntryEntity> dbSource = journalDao.getById(entryId);
        result.addSource(dbSource, entity -> {
            if (entity != null) {
                result.setValue(Resource.success(entity));
            } else {
                // Fallback to network
                fetchRemoteEntryAndCache(entryId, userId, result);
            }
        });

        return result;
    }

    /**
     * Creates a journal entry, handling offline queuing if network is unavailable.
     */
    public LiveData<Resource<JournalEntryEntity>> createJournalEntry(@NonNull final JournalEntryEntity entry) {
        return performUpsert(entry, /*isCreate=*/true);
    }

    /**
     * Updates an existing journal entry, handling offline syncing if network is unavailable.
     */
    public LiveData<Resource<JournalEntryEntity>> updateJournalEntry(@NonNull final JournalEntryEntity entry) {
        return performUpsert(entry, /*isCreate=*/false);
    }

    /**
     * Deletes the journal entry both locally and remotely (if online).
     */
    public LiveData<Resource<Void>> deleteJournalEntry(@NonNull final JournalEntryEntity entry) {

        final MutableLiveData<Resource<Void>> liveResult = new MutableLiveData<>();
        liveResult.postValue(Resource.loading(null));

        executors.diskIO().execute(() -> {
            journalDao.delete(entry);
            liveResult.postValue(Resource.success(null));

            if (connectivityChecker.isConnected()) {
                executors.networkIO().execute(() -> {
                    try {
                        Response<Void> response = apiService.deleteEntry(entry.getId()).execute();
                        if (!response.isSuccessful()) {
                            Logger.w(TAG, "deleteJournalEntry() remote call failed: " + response.code());
                            // Revert deletion locally if server failed
                            liveResult.postValue(Resource.error("Server rejected deletion", null));
                            journalDao.insert(entry);
                        }
                    } catch (IOException e) {
                        Logger.e(TAG, "deleteJournalEntry() network IO exception", e);
                        liveResult.postValue(Resource.error("Network error: " + e.getMessage(), null));
                        // Revert deletion because network failed
                        journalDao.insert(entry);
                    }
                });
            } else {
                // Mark entry as pendingDelete for later Worker sync
                journalDao.flagAsDeleted(entry.getId(), true);
            }
        });

        return liveResult;
    }

    /**
     * Triggers a full one-way sync to push local changes that are pendingSync = true
     * and to pull latest data from server. Intended to run inside a WorkManager Worker.
     */
    @WorkerThread
    public void performFullSync(@NonNull final String userId) {
        if (!connectivityChecker.isConnected()) {
            Logger.i(TAG, "performFullSync() skipped – offline");
            return;
        }

        final List<JournalEntryEntity> pendingUpserts = journalDao.getPendingUpserts(userId);
        final List<JournalEntryEntity> pendingDeletes = journalDao.getPendingDeletes(userId);

        // 1) Push local upserts
        for (JournalEntryEntity entity : pendingUpserts) {
            try {
                JournalEntryDto dto = mapper.toDto(entity);
                Response<JournalEntryDto> response = entity.isLocallyCreated()
                        ? apiService.postEntry(dto).execute()
                        : apiService.putEntry(entity.getId(), dto).execute();

                if (response.isSuccessful() && response.body() != null) {
                    JournalEntryEntity syncedEntity = mapper.toEntity(response.body());
                    syncedEntity.setPendingSync(false);
                    syncedEntity.setLocallyCreated(false);
                    journalDao.insertOrReplace(syncedEntity);
                }
            } catch (IOException e) {
                Logger.e(TAG, "performFullSync() failed pushing entry " + entity.getId(), e);
                // keep pendingSync flag set so next attempt will retry
            }
        }

        // 2) Push local deletes
        for (JournalEntryEntity entity : pendingDeletes) {
            try {
                Response<Void> response = apiService.deleteEntry(entity.getId()).execute();
                if (response.isSuccessful()) {
                    journalDao.delete(entity);
                }
            } catch (IOException e) {
                Logger.e(TAG, "performFullSync() failed deleting entry " + entity.getId(), e);
            }
        }

        // 3) Pull remote changes
        try {
            Response<List<JournalEntryDto>> response = apiService.getAllEntries(userId).execute();
            if (response.isSuccessful() && response.body() != null) {
                List<JournalEntryEntity> remoteEntities = mapper.toEntity(response.body());
                journalDao.replaceAllForUser(userId, remoteEntities);
            }
        } catch (IOException e) {
            Logger.e(TAG, "performFullSync() failed pulling entries", e);
        }
    }

    // -----------------------------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------------------------

    private LiveData<Resource<JournalEntryEntity>> performUpsert(@NonNull final JournalEntryEntity entry,
                                                                 final boolean isCreate) {

        final MutableLiveData<Resource<JournalEntryEntity>> liveResult = new MutableLiveData<>();
        liveResult.postValue(Resource.loading(null));

        // Assign ID for offline create
        if (isCreate && entry.getId() == null) {
            entry.setId(UUID.randomUUID().toString());
            entry.setLocallyCreated(true);
        }

        executors.diskIO().execute(() -> {
            // Write immediately to local DB for responsive UI
            entry.setPendingSync(!connectivityChecker.isConnected());
            journalDao.insertOrReplace(entry);
            liveResult.postValue(Resource.success(entry));

            if (connectivityChecker.isConnected()) {
                executors.networkIO().execute(() -> {
                    try {
                        JournalEntryDto dto = mapper.toDto(entry);
                        Response<JournalEntryDto> response = isCreate
                                ? apiService.postEntry(dto).execute()
                                : apiService.putEntry(entry.getId(), dto).execute();

                        if (response.isSuccessful() && response.body() != null) {
                            JournalEntryEntity syncedEntity = mapper.toEntity(response.body());
                            syncedEntity.setPendingSync(false);
                            syncedEntity.setLocallyCreated(false);
                            journalDao.insertOrReplace(syncedEntity);
                            liveResult.postValue(Resource.success(syncedEntity));
                        } else {
                            Logger.w(TAG, "performUpsert() remote call failed: " + response.code());
                            liveResult.postValue(Resource.error("Server error " + response.code(), entry));
                            // Leave entry flagged as pendingSync
                            entry.setPendingSync(true);
                            journalDao.insertOrReplace(entry);
                        }
                    } catch (IOException e) {
                        Logger.e(TAG, "performUpsert() network IO exception", e);
                        liveResult.postValue(Resource.error("Network error: " + e.getMessage(), entry));
                        // Mark for later sync
                        entry.setPendingSync(true);
                        journalDao.insertOrReplace(entry);
                    }
                });
            }
        });

        return liveResult;
    }

    private void fetchRemoteEntryAndCache(@NonNull String entryId,
                                          @NonNull String userId,
                                          @NonNull MediatorLiveData<Resource<JournalEntryEntity>> result) {

        if (!connectivityChecker.isConnected()) {
            result.postValue(Resource.error("Offline and entry not in cache", null));
            return;
        }

        executors.networkIO().execute(() -> {
            try {
                Response<JournalEntryDto> response = apiService.getEntryById(entryId).execute();
                if (response.isSuccessful() && response.body() != null) {
                    JournalEntryEntity entity = mapper.toEntity(response.body());
                    journalDao.insertOrReplace(entity);
                    result.postValue(Resource.success(entity));
                } else {
                    Logger.w(TAG, "fetchRemoteEntryAndCache() call failed: " + response.code());
                    result.postValue(Resource.error("Server error " + response.code(), null));
                }
            } catch (IOException e) {
                Logger.e(TAG, "fetchRemoteEntryAndCache() network IO exception", e);
                result.postValue(Resource.error("Network error: " + e.getMessage(), null));
            }
        });
    }

    // -----------------------------------------------------------------------------------------
    // For unit-test visibility
    // -----------------------------------------------------------------------------------------

    @VisibleForTesting(otherwise = VisibleForTesting.NONE)
    void clearInstance() {
        INSTANCE = null;
    }
}