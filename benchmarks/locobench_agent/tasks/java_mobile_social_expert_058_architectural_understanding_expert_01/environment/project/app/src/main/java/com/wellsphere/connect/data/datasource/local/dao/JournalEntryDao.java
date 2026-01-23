```java
package com.wellsphere.connect.data.datasource.local.dao;

import androidx.annotation.IntDef;
import androidx.annotation.NonNull;
import androidx.annotation.VisibleForTesting;
import androidx.room.Dao;
import androidx.room.Delete;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;
import androidx.room.Transaction;
import androidx.room.Update;

import com.wellsphere.connect.data.datasource.local.entity.JournalEntryEntity;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.util.List;

import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.core.Flowable;
import io.reactivex.rxjava3.core.Maybe;
import io.reactivex.rxjava3.core.Single;

/**
 * JournalEntryDao provides type-safe database access for {@link JournalEntryEntity}.
 *
 * Design notes:
 * • RxJava 3 is used as the reactive primitive to enable cancellation and back-pressure support.
 * • All queries are scoped to a {@code userId} to prevent data leaks between multi-account users.
 * • Sync-state helpers allow the Repository layer to orchestrate cloud/Room reconciliation.
 */
@Dao
public interface JournalEntryDao {

    /* ---------------------------------------- *
     *               SYNC STATES                *
     * ---------------------------------------- */
    @Retention(RetentionPolicy.SOURCE)
    @IntDef({SYNC_STATE_PENDING, SYNC_STATE_IN_PROGRESS, SYNC_STATE_ERROR, SYNC_STATE_SYNCED})
    @interface SyncState {}

    /** Item was created/updated locally and is waiting to be sent to the backend. */
    int SYNC_STATE_PENDING     = 0;

    /** A background worker is currently pushing the item to the backend.        */
    int SYNC_STATE_IN_PROGRESS = 1;

    /** Last sync attempt failed, user/device is offline, etc.                   */
    int SYNC_STATE_ERROR       = 2;

    /** Item is fully synced with backend and considered source-of-truth.        */
    int SYNC_STATE_SYNCED      = 3;

    /* ---------------------------------------- *
     *                OBSERVERS                 *
     * ---------------------------------------- */

    /**
     * Stream all journal entries for a user ordered by creation date, newest first.
     *
     * The resulting {@link Flowable} emits a new list every time the underlying table mutates.
     */
    @NonNull
    @Query("SELECT * FROM journal_entries "
         + "WHERE user_id = :userId "
         + "ORDER BY created_at DESC")
    Flowable<List<JournalEntryEntity>> watchAll(long userId);

    /**
     * Stream only the journal entries that have not been successfully synced.
     */
    @NonNull
    @Query("SELECT * FROM journal_entries "
         + "WHERE sync_state != " + SYNC_STATE_SYNCED + " "
         + "AND user_id = :userId "
         + "ORDER BY created_at ASC")
    Flowable<List<JournalEntryEntity>> watchPendingSync(long userId);

    /**
     * Observe a single entry by its database id.
     */
    @NonNull
    @Query("SELECT * FROM journal_entries WHERE entry_id = :entryId LIMIT 1")
    Maybe<JournalEntryEntity> watchById(long entryId);

    /* ---------------------------------------- *
     *                 QUERIES                  *
     * ---------------------------------------- */

    /**
     * Search by keyword in the title OR body for the given user.
     */
    @NonNull
    @Query("SELECT * FROM journal_entries "
         + "WHERE user_id = :userId "
         + "AND (title LIKE '%' || :keyword || '%' "
         + "OR body  LIKE '%' || :keyword || '%') "
         + "ORDER BY created_at DESC")
    Flowable<List<JournalEntryEntity>> search(long userId, @NonNull String keyword);

    /**
     * Synchronously fetch a single entry.  Intended for one-shot calls (e.g. Worker).
     */
    @NonNull
    @Query("SELECT * FROM journal_entries WHERE entry_id = :entryId LIMIT 1")
    Single<JournalEntryEntity> getById(long entryId);

    /* ---------------------------------------- *
     *            INSERT / UPDATE / DELETE      *
     * ---------------------------------------- */

    /**
     * Insert a new journal entry.  REPLACE strategy allows "offline upsert" semantics
     * when the client generates its own {@code entry_id}.
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    Single<Long> insert(@NonNull JournalEntryEntity entry);

    /**
     * Bulk insert with the same semantics as {@link #insert(JournalEntryEntity)}.
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    Single<List<Long>> insert(@NonNull List<JournalEntryEntity> entries);

    /**
     * Update an existing entry by primary key.  Returns the number of rows affected.
     */
    @Update
    Single<Integer> update(@NonNull JournalEntryEntity entry);

    /**
     * Mark the given entries with a new sync-state.
     */
    @Query("UPDATE journal_entries "
         + "SET sync_state = :newState, "
         + "    updated_at = :timestamp "
         + "WHERE entry_id IN (:entryIds)")
    Completable setSyncState(@NonNull List<Long> entryIds,
                             @SyncState int newState,
                             long timestamp);

    /**
     * Deletes a single entry.
     */
    @Delete
    Single<Integer> delete(@NonNull JournalEntryEntity entry);

    /**
     * Purge old, already-synced entries to free local storage.
     *
     * @param epochCutoff  All entries whose {@code updated_at} is &lt; cutoff are removed
     *                     IF their {@code sync_state} equals {@link #SYNC_STATE_SYNCED}.
     */
    @Query("DELETE FROM journal_entries "
         + "WHERE updated_at < :epochCutoff "
         + "AND   sync_state = " + SYNC_STATE_SYNCED)
    Single<Integer> pruneSyncedBefore(long epochCutoff);

    /* ---------------------------------------- *
     *                UPSERT API                *
     * ---------------------------------------- */

    /**
     * Convenience upsert that first tries to insert and falls back to update if the insert
     * returns a conflict (RowId == -1).  Room does not (yet) support native upsert, therefore
     * we need a transactional workaround.
     */
    @Transaction
    default Single<Long> upsert(@NonNull JournalEntryEntity entry) {
        // Use defer() so that the DB work is executed lazily on subscription.
        return Single.defer(() -> insert(entry)
                .flatMap(id -> {
                    // When OnConflictStrategy.REPLACE is used, Room returns the id of the row.
                    // We consider a successful insert if id != -1.
                    if (id != -1L) {
                        return Single.just(id);
                    }
                    // Otherwise perform an explicit update.
                    return update(entry).map(rows -> entry.getEntryId());
                }));
    }

    /* ---------------------------------------- *
     *         TESTING / DEBUG UTILITIES        *
     * ---------------------------------------- */

    /**
     * Clear the entire table.  Restricted to debug/benchmark modules.
     */
    @VisibleForTesting
    @Query("DELETE FROM journal_entries")
    Single<Integer> nukeTable();
}
```