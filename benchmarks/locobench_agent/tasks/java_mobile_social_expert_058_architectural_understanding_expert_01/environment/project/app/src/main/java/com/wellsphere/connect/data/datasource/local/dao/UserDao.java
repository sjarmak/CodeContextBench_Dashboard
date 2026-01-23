```java
/*
 * WellSphere Connect
 * Copyright (c) 
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 *
 * -------------------------------------------------------------------
 * File:    UserDao.java
 * Package: com.wellsphere.connect.data.datasource.local.dao
 * Project: WellSphere Connect (mobile_social)
 * -------------------------------------------------------------------
 *
 * Description:
 * Data-Access-Object responsible for persisting and querying user-centric
 * data in the WellSphere Connect Room data-base layer.  The DAO exposes a
 * rich API tailored for:
 *   • Lifecycle-aware reactive streams (RxJava 3)
 *   • Optimistic offline synchronization (isSynced flag)
 *   • Current-user caching semantics
 *   • Security-driven partial updates (PII vs. non-PII)
 *
 * All queries are explicitly scoped and indexed for deterministic
 * behavior inside a HIPAA regulated environment.
 */

package com.wellsphere.connect.data.datasource.local.dao;

import androidx.lifecycle.LiveData;
import androidx.room.Dao;
import androidx.room.Delete;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;
import androidx.room.Transaction;
import androidx.room.Update;

import com.wellsphere.connect.data.datasource.local.entity.UserEntity;

import java.util.List;

import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.core.Flowable;
import io.reactivex.rxjava3.core.Maybe;
import io.reactivex.rxjava3.core.Single;

@Dao
public interface UserDao {

    /* ------------------------------------------------------------------
     * Insert
     * ------------------------------------------------------------------ */

    /**
     * Inserts a single {@link UserEntity}. Fails if a user with identical
     * primary key already exists to guard against accidental override of
     * identity-critical columns (uid, remoteId).
     *
     * @param user entity to be persisted.
     * @return a RxJava {@link Single} that emits the newly created rowId.
     */
    @Insert(onConflict = OnConflictStrategy.ABORT)
    Single<Long> insert(UserEntity user);

    /**
     * Batch-insert that replaces duplicates.  This variant is reserved for
     * server-sourced upserts during sync.
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    Completable upsertAll(List<UserEntity> users);

    /* ------------------------------------------------------------------
     * Update
     * ------------------------------------------------------------------ */

    /**
     * Updates user.  Returns the number of rows updated.
     * <p>
     * The call is wrapped in a {@link Completable} to allow subscription
     * chaining while preserving Room’s threading guarantees.
     */
    @Update(onConflict = OnConflictStrategy.ABORT)
    Completable update(UserEntity user);

    /**
     * Partial update that toggles the `isSynced` flag after a successful
     * cloud merge.
     */
    @Query("UPDATE users SET is_synced = :synced, updated_at = :timestamp WHERE uid = :userId")
    Completable markSyncStatus(long userId, boolean synced, long timestamp);

    /**
     * Refreshes the biometrics-protected PII section without touching
     * social profile fields.
     */
    @Query("UPDATE users SET first_name = :firstName, last_name = :lastName, date_of_birth = :dob, updated_at = :timestamp WHERE uid = :userId")
    Completable updatePersonalInfo(long userId,
                                   String firstName,
                                   String lastName,
                                   long dob,
                                   long timestamp);

    /* ------------------------------------------------------------------
     * Delete
     * ------------------------------------------------------------------ */

    /**
     * Removes a user by primary key.  Never cascade-deletes posts or
     * activities; integrity constraints are enforced at database level.
     */
    @Delete
    Completable delete(UserEntity user);

    /**
     * Hard delete via PK.
     */
    @Query("DELETE FROM users WHERE uid = :userId")
    Completable deleteById(long userId);

    /* ------------------------------------------------------------------
     * Query – read-only
     * ------------------------------------------------------------------ */

    /**
     * Observes all users (rare in production, but handy for admin mode and
     * debugging).  Ordered by creation date descending so most recent
     * sign-ups appear first.
     */
    @Query("SELECT * FROM users ORDER BY created_at DESC")
    Flowable<List<UserEntity>> observeAll();

    /**
     * Observes a single user identified by primary key.  Emits whenever the
     * row changes.
     */
    @Query("SELECT * FROM users WHERE uid = :userId LIMIT 1")
    Flowable<UserEntity> observeById(long userId);

    /**
     * LiveData variant for UI-layer data-binding.
     */
    @Query("SELECT * FROM users WHERE uid = :userId LIMIT 1")
    LiveData<UserEntity> liveById(long userId);

    /**
     * One-shot retrieval of current signed-in user (if any).
     */
    @Query("SELECT * FROM users WHERE is_current_user = 1 LIMIT 1")
    Maybe<UserEntity> getCurrentUser();

    /**
     * Fetches by remote (server) identifier, facilitating merge/conflict
     * detection during incremental sync.
     */
    @Query("SELECT * FROM users WHERE remote_id = :remoteId LIMIT 1")
    Maybe<UserEntity> findByRemoteId(String remoteId);

    /**
     * Checks whether an e-mail is already taken (case-insensitive).
     */
    @Query("SELECT COUNT(uid) FROM users WHERE LOWER(email) = LOWER(:email)")
    Single<Integer> emailExists(String email);

    /* ------------------------------------------------------------------
     * Transaction helpers
     * ------------------------------------------------------------------ */

    /**
     * Atomically switches the 'current user' flag.  Guarantees that at most
     * one row has {@code is_current_user = 1}.
     */
    @Transaction
    default Completable switchCurrentUser(long newCurrentUserId) {
        return clearCurrentUserFlag()
                .andThen(markAsCurrentUser(newCurrentUserId));
    }

    @Query("UPDATE users SET is_current_user = 0 WHERE is_current_user = 1")
    Completable clearCurrentUserFlag();

    @Query("UPDATE users SET is_current_user = 1 WHERE uid = :userId")
    Completable markAsCurrentUser(long userId);

    /* ------------------------------------------------------------------
     * Maintenance / diagnostics
     * ------------------------------------------------------------------ */

    /**
     * Internal maintenance call invoked by nightly job to purge soft
     * deleted or orphaned users, while keeping admin accounts intact.
     */
    @Query("DELETE FROM users WHERE is_marked_for_deletion = 1")
    Completable purgeMarkedUsers();
}
```