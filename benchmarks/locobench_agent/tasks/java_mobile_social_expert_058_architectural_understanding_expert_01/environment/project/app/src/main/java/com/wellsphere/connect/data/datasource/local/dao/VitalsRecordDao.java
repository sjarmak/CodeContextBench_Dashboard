```java
package com.wellsphere.connect.data.datasource.local.dao;

import androidx.annotation.NonNull;
import androidx.annotation.VisibleForTesting;
import androidx.lifecycle.LiveData;
import androidx.paging.DataSource;
import androidx.room.*;
import io.reactivex.Completable;
import io.reactivex.Flowable;
import io.reactivex.Single;

import com.wellsphere.connect.data.datasource.local.entities.VitalsRecordEntity;

import java.util.Collection;
import java.util.Date;
import java.util.List;

/**
 * Room Data-Access-Object for {@link VitalsRecordEntity}.
 * <p>
 * NOTE:
 *  • All date parameters are expected to be in UTC (milliseconds since epoch).<br>
 *  • RxJava is used for all async/streaming access to ensure non-blocking DB operations.<br>
 *  • {@link Transaction} is applied tactically to guarantee atomic writes across multi-step calls.
 *
 * Created by WellSphere Connect – code-gen/AI + human review.
 */
@Dao
public interface VitalsRecordDao {

    /* ************************************************************
     * Inserts
     * ************************************************************/

    /**
     * Inserts or replaces a single vitals record.
     *
     * @return Row id of the newly inserted item.
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    long insert(@NonNull VitalsRecordEntity entity);

    /**
     * Inserts a collection of vitals records within a DB transaction.
     *
     * @return Row ids of the inserted items.
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    long[] insert(@NonNull List<VitalsRecordEntity> entities);

    /**
     * RxJava wrapper around {@link #insert(List)}.
     */
    @Transaction
    default Single<long[]> insertReactive(@NonNull final List<VitalsRecordEntity> entities) {
        return Single.fromCallable(() -> insert(entities));
    }

    /* ************************************************************
     * Updates
     * ************************************************************/

    /**
     * Update an existing record.
     *
     * @return Number of rows affected.
     */
    @Update(onConflict = OnConflictStrategy.ABORT)
    int update(@NonNull VitalsRecordEntity entity);

    /**
     * Mark multiple records as synced while attaching their server-side identifiers.
     *
     * @param localIds   Set of local (client-generated) ids to update.
     * @param remoteId   Corresponding EHR/Server id (may be null for bulk update of same id column).
     * @param syncedAt   Timestamp when server acknowledged the record.
     */
    @Query("UPDATE vitals_records " +
           "SET remote_id = CASE WHEN :remoteId IS NOT NULL THEN :remoteId ELSE remote_id END, " +
           "    synced     = 1, " +
           "    synced_at  = :syncedAt " +
           "WHERE local_id IN (:localIds)")
    void markRecordsAsSynced(@NonNull Collection<String> localIds,
                             String remoteId,
                             long syncedAt);

    /**
     * RxJava convenience method to mark records as synced.
     */
    @Transaction
    default Completable markRecordsAsSyncedReactive(@NonNull Collection<String> localIds,
                                                    String remoteId,
                                                    long syncedAt) {
        return Completable.fromAction(() -> markRecordsAsSynced(localIds, remoteId, syncedAt));
    }

    /* ************************************************************
     * Deletes
     * ************************************************************/

    @Delete
    int delete(@NonNull VitalsRecordEntity entity);

    @Query("DELETE FROM vitals_records WHERE local_id IN (:localIds)")
    int deleteByIds(@NonNull Collection<String> localIds);

    /* ************************************************************
     * Query helpers
     * ************************************************************/

    /**
     * Fetch unsynced records for a patient to be pushed to server.
     */
    @Query("SELECT * FROM vitals_records " +
           "WHERE patient_id = :patientId " +
           "  AND synced = 0")
    Single<List<VitalsRecordEntity>> getUnsyncedRecords(@NonNull String patientId);

    /**
     * Reactive stream of latest records per vital type.
     *
     * @param patientId Patient identifier
     * @param vitalType E.g. BLOOD_PRESSURE, HEART_RATE
     * @param limit     Number of rows to keep
     */
    @Query("SELECT * FROM vitals_records " +
           "WHERE patient_id = :patientId " +
           "  AND vital_type = :vitalType " +
           "ORDER BY recorded_at DESC " +
           "LIMIT :limit")
    Flowable<List<VitalsRecordEntity>> observeLatestRecords(@NonNull String patientId,
                                                            @NonNull String vitalType,
                                                            int limit);

    /**
     * Range query (inclusive) returning LiveData for UI binding.
     */
    @Query("SELECT * FROM vitals_records " +
           "WHERE patient_id = :patientId " +
           "  AND vital_type = :vitalType " +
           "  AND recorded_at BETWEEN :from AND :to " +
           "ORDER BY recorded_at ASC")
    LiveData<List<VitalsRecordEntity>> getRecordsInRange(@NonNull String patientId,
                                                         @NonNull String vitalType,
                                                         long from,
                                                         long to);

    /**
     * Paging source factory used by Jetpack Paging3.
     * Sorted DESC to display newest first.
     */
    @Query("SELECT * FROM vitals_records " +
           "WHERE patient_id = :patientId " +
           "  AND vital_type = :vitalType " +
           "ORDER BY recorded_at DESC")
    DataSource.Factory<Integer, VitalsRecordEntity> pagingSource(@NonNull String patientId,
                                                                 @NonNull String vitalType);

    /* ************************************************************
     * Diagnostics helpers
     * ************************************************************/

    /**
     * This method is only exposed to Instrumentation & Robolectric tests.
     */
    @VisibleForTesting(otherwise = VisibleForTesting.NONE)
    @Query("DELETE FROM vitals_records")
    void clearAllForTesting();

    @VisibleForTesting(otherwise = VisibleForTesting.NONE)
    @Query("SELECT COUNT(*) FROM vitals_records")
    int countAll();
}
```