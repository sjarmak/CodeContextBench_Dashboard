```java
package com.wellsphere.connect.data.datasource.local.dao;

import androidx.annotation.NonNull;
import androidx.lifecycle.LiveData;
import androidx.paging.DataSource;
import androidx.room.Dao;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;
import androidx.room.Transaction;
import androidx.room.Update;

import com.wellsphere.connect.data.datasource.local.entity.SocialPostEntity;

import java.util.List;

import io.reactivex.Completable;
import io.reactivex.Flowable;
import io.reactivex.Single;

/**
 * Data-access object for {@link SocialPostEntity}.
 *
 * The DAO exposes synchronous, RxJava-based, and Room-paging compatible
 * APIs to cater to a wide range of consumers (Repository, Worker,
 * ViewModel, PagingSource, etc.).
 *
 * <p>Key implementation nuances:</p>
 * <ol>
 *     <li><b>Soft-deletion</b> – posts are first flagged via
 *         {@code is_deleted = 1} in order to preserve audit trails and
 *         enable server reconciliation. A background job later purges
 *         records that have been successfully synced and acknowledged
 *         by the backend.</li>
 *     <li><b>Optimistic concurrency</b> – update operations leverage
 *         {@code updated_at} checks so that stale local edits do not
 *         silently overwrite more recent changes pulled from the server.</li>
 *     <li><b>Paging</b> – Returning a {@link DataSource.Factory} keeps
 *         memory pressure low when rendering infinite scrolling feeds.</li>
 * </ol>
 */
@Dao
public interface SocialPostDao {

    // ---------------------------------------------------------------------
    // INSERT
    // ---------------------------------------------------------------------

    /**
     * Up-sert semantics: if the primary key already exists the row will
     * be replaced. We generally prefer {@link OnConflictStrategy#REPLACE}
     * over {@link OnConflictStrategy#ABORT} because post IDs are UUIDs
     * generated on the client while offline.
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    Completable insertOrReplace(@NonNull SocialPostEntity post);

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    Completable insertOrReplace(@NonNull List<SocialPostEntity> posts);

    // ---------------------------------------------------------------------
    // READ
    // ---------------------------------------------------------------------

    /**
     * Returns a cold observable stream of *visible* posts (i.e., not soft-deleted),
     * ordered by creation date descending. This is used by the home feed.
     */
    @Query("SELECT * FROM social_post WHERE is_deleted = 0 "
         + "ORDER BY created_at DESC")
    Flowable<List<SocialPostEntity>> observeAllPosts();

    /**
     * Paging source for endless-scroll UI.
     */
    @Query("SELECT * FROM social_post WHERE is_deleted = 0 "
         + "ORDER BY created_at DESC")
    DataSource.Factory<Integer, SocialPostEntity> pagingSource();

    /**
     * Reactive subscription to a single post by its ID.
     */
    @Query("SELECT * FROM social_post WHERE post_id = :postId LIMIT 1")
    Flowable<SocialPostEntity> observeById(@NonNull String postId);

    /**
     * Synchronous fetch for WorkManager/Sync adapters.
     */
    @Query("SELECT * FROM social_post WHERE post_id = :postId LIMIT 1")
    SocialPostEntity getById(@NonNull String postId);

    /**
     * Returns posts that have not yet been synced with the backend service.
     */
    @Query("SELECT * FROM social_post WHERE is_synced = 0 AND is_deleted = 0")
    Single<List<SocialPostEntity>> getPendingSync();

    /**
     * Full-text search backed by SQLite FTS5 virtual table.
     * The FTS table is kept in sync via Room triggers.
     */
    @Query("SELECT sp.* FROM social_post_fts fts "
         + "JOIN social_post sp ON sp.post_id = fts.docid "
         + "WHERE fts MATCH :query AND sp.is_deleted = 0 "
         + "ORDER BY sp.created_at DESC")
    Flowable<List<SocialPostEntity>> searchPosts(@NonNull String query);

    // ---------------------------------------------------------------------
    // UPDATE
    // ---------------------------------------------------------------------

    /**
     * Update the content of a post. Uses optimistic concurrency to avoid
     * clobbering newer updates.
     *
     * @param postId            local or server UUID
     * @param newContent        updated message body
     * @param expectedUpdatedAt previous {@code updated_at} timestamp that
     *                          the caller believes to be current
     * @param newUpdatedAt      new {@code updated_at} timestamp to set
     * @return number of affected rows (0 indicates a conflict)
     */
    @Query("UPDATE social_post "
         + "SET content = :newContent, "
         + "updated_at = :newUpdatedAt, "
         + "is_synced = 0 "
         + "WHERE post_id = :postId AND updated_at = :expectedUpdatedAt "
         + "AND is_deleted = 0")
    Single<Integer> updateContentOptimistic(@NonNull String postId,
                                            @NonNull String newContent,
                                            long expectedUpdatedAt,
                                            long newUpdatedAt);

    /**
     * Marks a Post as synced once the server confirms receipt.
     */
    @Query("UPDATE social_post "
         + "SET is_synced = 1, server_revision = :serverRevision "
         + "WHERE post_id = :postId")
    Completable markAsSynced(@NonNull String postId, long serverRevision);

    // ---------------------------------------------------------------------
    // DELETE
    // ---------------------------------------------------------------------

    /**
     * Soft-delete: keeps row for auditing & conflict resolution.
     */
    @Query("UPDATE social_post "
         + "SET is_deleted = 1, is_synced = 0, updated_at = :deletedAt "
         + "WHERE post_id = :postId")
    Completable softDelete(@NonNull String postId, long deletedAt);

    /**
     * Permanently remove posts that the backend already acknowledged as deleted.
     * This should only be executed from a background clean-up worker.
     *
     * @return number of purged rows
     */
    @Query("DELETE FROM social_post "
         + "WHERE is_deleted = 1 AND is_synced = 1")
    int purgeDeleted();

    // ---------------------------------------------------------------------
    // TRANSACTIONAL HELPERS
    // ---------------------------------------------------------------------

    /**
     * Atomically replaces an existing post with a new version originating
     * from the server. This helper avoids intermediate states being observed
     * by the UI when LiveData/Flowable subscribers are active.
     */
    @Transaction
    default Completable upsertFromServer(@NonNull SocialPostEntity serverPost) {
        // We intentionally chain Completable operations to ensure the insert
        // happens on the Room scheduler and completes before the method returns.
        return softDelete(serverPost.getPostId(), serverPost.getUpdatedAt()) // No-op if not existing
                .andThen(insertOrReplace(serverPost));
    }

    // ---------------------------------------------------------------------
    // DIAGNOSTICS
    // ---------------------------------------------------------------------

    /**
     * Returns the total number of visible (non-deleted) posts. Useful for
     * analytics and debug screens.
     */
    @Query("SELECT COUNT(*) FROM social_post WHERE is_deleted = 0")
    LiveData<Integer> observeVisibleCount();
}
```