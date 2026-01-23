package com.wellsphere.connect.data.repository;

import android.annotation.SuppressLint;

import androidx.annotation.MainThread;
import androidx.annotation.NonNull;
import androidx.annotation.VisibleForTesting;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MediatorLiveData;

import com.wellsphere.connect.data.db.dao.CarePlanDao;
import com.wellsphere.connect.data.db.entity.CarePlanEntity;
import com.wellsphere.connect.data.model.CarePlan;
import com.wellsphere.connect.data.remote.Resource;
import com.wellsphere.connect.data.remote.network.ApiResponse;
import com.wellsphere.connect.data.remote.network.CarePlanApiService;
import com.wellsphere.connect.util.NetworkStatusProvider;
import com.wellsphere.connect.util.PreferenceStore;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import timber.log.Timber;

/**
 * Repository that manages CarePlan data for both local (Room) and remote (REST) sources.
 *
 * <p>
 * Responsibilities:
 * 1. Decide whether data should be fetched from network or database cache.
 * 2. Perform two-way sync of user mutations created while offline.
 * 3. Expose lifecycle-aware, observable streams to ViewModels.
 * </p>
 *
 * Thread model:
 *  - Room operations run on a dedicated IO executor.
 *  - Retrofit callbacks are marshalled back onto the same IO executor before
 *    dispatching results to the main thread via LiveData.
 */
public class CarePlanRepository {

    private static final long CARE_PLAN_STALE_THRESHOLD_MS = 4 * 60 * 60 * 1000; // 4 hours

    private static volatile CarePlanRepository instance;

    private final CarePlanDao carePlanDao;
    private final CarePlanApiService apiService;
    private final NetworkStatusProvider networkStatusProvider;
    private final PreferenceStore preferenceStore;

    // Single threaded executor is sufficient because Room handles its own
    // synchronization and care plans are a small data set.
    private final ExecutorService ioExecutor = Executors.newSingleThreadExecutor();

    @SuppressLint("RestrictedApi")
    private CarePlanRepository(@NonNull CarePlanDao dao,
                               @NonNull CarePlanApiService api,
                               @NonNull NetworkStatusProvider networkStatusProvider,
                               @NonNull PreferenceStore preferenceStore) {
        this.carePlanDao = dao;
        this.apiService = api;
        this.networkStatusProvider = networkStatusProvider;
        this.preferenceStore = preferenceStore;
    }

    /* ====================================================================== */
    /*  Public  API                                                           */
    /* ====================================================================== */

    /**
     * Returns a reactive stream of CarePlans for a patient. Whenever local DB
     * changes, observers will receive an updated list.
     *
     * @param patientId   Unique identifier of the patient whose care plans are requested
     * @param forceRefresh If true, always fetch fresh data from server ignoring cache age
     */
    @MainThread
    public LiveData<Resource<List<CarePlan>>> getCarePlans(@NonNull final String patientId,
                                                           final boolean forceRefresh) {
        final MediatorLiveData<Resource<List<CarePlan>>> result = new MediatorLiveData<>();
        result.setValue(Resource.loading());

        // Step 1: Listen to local DB
        final LiveData<List<CarePlanEntity>> dbSource = carePlanDao.observeByPatient(patientId);

        result.addSource(dbSource, entities -> {
            List<CarePlan> mapped = mapToDomain(entities);
            result.setValue(Resource.success(mapped));
        });

        // Step 2: Decide whether we need network refresh
        boolean shouldFetch = shouldFetchFromNetwork(patientId, forceRefresh);
        if (shouldFetch && networkStatusProvider.isOnline()) {
            fetchFromNetworkAndPersist(patientId, result);
        } else if (shouldFetch) {
            // We're offline and cache is stale. Signal to UI so it can show proper messaging.
            result.setValue(Resource.error(Resource.ErrorCode.NO_NETWORK,
                                           "Offline and cache is stale", null));
        }

        return result;
    }

    /**
     * Force-refresh care plans from the backend irrespective of cache state.
     */
    @MainThread
    public LiveData<Resource<Void>> refreshCarePlans(@NonNull String patientId) {
        MediatorLiveData<Resource<Void>> liveData = new MediatorLiveData<>();
        liveData.setValue(Resource.loading());

        if (!networkStatusProvider.isOnline()) {
            liveData.setValue(Resource
                    .error(Resource.ErrorCode.NO_NETWORK, "No internet connection", null));
            return liveData;
        }

        fetchFromNetworkAndPersist(patientId, liveData);
        return liveData;
    }

    /**
     * Pushes locally created or updated care plans to backend. Should be called
     * periodically via WorkManager when connectivity is available.
     */
    public void syncPendingCarePlans() {
        ioExecutor.execute(() -> {
            List<CarePlanEntity> pending = carePlanDao.loadPendingSync();
            if (pending.isEmpty()) return;

            for (CarePlanEntity entity : pending) {
                CarePlan payload = entity.toDomain();
                Call<ApiResponse<CarePlan>> call = apiService.upsertCarePlan(payload);
                try {
                    Response<ApiResponse<CarePlan>> response = call.execute();
                    if (response.isSuccessful() && response.body() != null) {
                        // Server may have mutated the plan (e.g., add remote id)
                        CarePlan updated = response.body().getData();
                        carePlanDao.replace(mapToEntity(updated, false));
                    } else {
                        Timber.w("Failed to upsert care plan %s – HTTP %d",
                                entity.getLocalId(), response.code());
                    }
                } catch (IOException e) {
                    Timber.e(e, "Sync failed for care plan %s", entity.getLocalId());
                    // Break early; we’ll retry later in a WorkManager back-off chain
                    break;
                }
            }
        });
    }

    /* ====================================================================== */
    /*  Internal helpers                                                      */
    /* ====================================================================== */

    private boolean shouldFetchFromNetwork(@NonNull String patientId, boolean force) {
        if (force) return true;

        long lastSyncUtc = preferenceStore.getLastCarePlanSync(patientId);
        long age = System.currentTimeMillis() - lastSyncUtc;
        return age > CARE_PLAN_STALE_THRESHOLD_MS;
    }

    /**
     * Fetches care plans from backend, persists them in DB,
     * and posts status updates to provided LiveData (if non-null)
     */
    private <T> void fetchFromNetworkAndPersist(@NonNull final String patientId,
                                                final MediatorLiveData<Resource<T>> liveData) {
        Call<ApiResponse<List<CarePlan>>> call = apiService.getCarePlans(patientId);

        call.enqueue(new Callback<ApiResponse<List<CarePlan>>>() {
            @Override
            public void onResponse(@NonNull Call<ApiResponse<List<CarePlan>>> call,
                                   @NonNull Response<ApiResponse<List<CarePlan>>> response) {

                if (!response.isSuccessful() || response.body() == null) {
                    Timber.e("Fetch care plans failed – HTTP %d", response.code());
                    postError(Resource.ErrorCode.SERVER_ERROR,
                              "Failed to load care plans", liveData);
                    return;
                }

                // Write to DB off-thread
                ioExecutor.execute(() -> {
                    List<CarePlan> plans = response.body().getData();
                    List<CarePlanEntity> entities = new ArrayList<>(plans.size());
                    for (CarePlan p : plans) {
                        entities.add(mapToEntity(p, false /*already synced*/));
                    }
                    carePlanDao.replaceAll(patientId, entities);

                    // Persist sync timestamp
                    preferenceStore.setLastCarePlanSync(patientId, System.currentTimeMillis());
                });

                if (liveData != null) {
                    liveData.postValue(Resource.success(null));
                }
            }

            @Override
            public void onFailure(@NonNull Call<ApiResponse<List<CarePlan>>> call,
                                  @NonNull Throwable t) {
                Timber.e(t, "Network request failed");
                postError(Resource.ErrorCode.NETWORK_IO, t.getMessage(), liveData);
            }
        });
    }

    private <T> void postError(Resource.ErrorCode code,
                               String message,
                               MediatorLiveData<Resource<T>> liveData) {
        if (liveData == null) return;
        liveData.postValue(Resource.error(code, message, null));
    }

    /* ====================================================================== */
    /*  Mapping helper methods                                                */
    /* ====================================================================== */

    @NonNull
    private List<CarePlan> mapToDomain(List<CarePlanEntity> entities) {
        if (entities == null) return Collections.emptyList();
        List<CarePlan> out = new ArrayList<>(entities.size());
        for (CarePlanEntity e : entities) out.add(e.toDomain());
        return out;
    }

    private CarePlanEntity mapToEntity(CarePlan plan, boolean pendingSync) {
        return CarePlanEntity.fromDomain(plan, pendingSync, new Date());
    }

    /* ====================================================================== */
    /*  Singleton instantiation                                               */
    /* ====================================================================== */

    public static CarePlanRepository getInstance(@NonNull CarePlanDao dao,
                                                 @NonNull CarePlanApiService api,
                                                 @NonNull NetworkStatusProvider networkStatusProvider,
                                                 @NonNull PreferenceStore preferenceStore) {
        if (instance == null) {
            synchronized (CarePlanRepository.class) {
                if (instance == null) {
                    instance = new CarePlanRepository(dao, api, networkStatusProvider,
                                                      preferenceStore);
                }
            }
        }
        return instance;
    }

    /* ====================================================================== */
    /*  Test helpers                                                          */
    /* ====================================================================== */

    @VisibleForTesting
    void clearInstance() {
        instance = null;
    }
}