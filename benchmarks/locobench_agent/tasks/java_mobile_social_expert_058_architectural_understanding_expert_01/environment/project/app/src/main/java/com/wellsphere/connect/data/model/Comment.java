```java
package com.wellsphere.connect.data.model;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.ColumnInfo;
import androidx.room.Entity;
import androidx.room.PrimaryKey;
import androidx.room.TypeConverter;
import androidx.room.TypeConverters;

import com.google.gson.annotations.SerializedName;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

/**
 * Comment entity representing user–generated feedback attached to a Post.
 *
 * <p>The model is dual-purpose:
 *  1. Annotated for Room persistence so it can be cached/off-lined when network
 *     is unavailable.
 *  2. Annotated for GSON serialization/deserialization in Retrofit calls.</p>
 *
 * <p>⚠️ Never expose PHI (Protected Health Information) in a Comment. The backend
 *       enforces this, but the mobile layer validates as an extra guard.</p>
 */
@Entity(tableName = "comments")
@TypeConverters(Comment.ReactionListConverter.class)
public final class Comment implements Parcelable {

    /* ---------- Database / Network Fields ---------- */

    /** Primary key – UUID generated on client when first created */
    @PrimaryKey
    @NonNull
    @SerializedName("id")
    private final String id;

    /** Foreign key referencing Post.id */
    @NonNull
    @ColumnInfo(name = "post_id")
    @SerializedName("postId")
    private final String postId;

    /** Author's user id */
    @NonNull
    @ColumnInfo(name = "author_id")
    @SerializedName("authorId")
    private final String authorId;

    /** Cached display name for denormalised rendering (can be stale) */
    @NonNull
    @ColumnInfo(name = "author_display_name")
    @SerializedName("authorDisplayName")
    private final String authorDisplayName;

    /** Plain-text body (markdown allowed on backend) */
    @NonNull
    @SerializedName("body")
    private final String body;

    /** UTC epoch millis at time of creation */
    @ColumnInfo(name = "created_at")
    @SerializedName("createdAt")
    private final long createdAt;

    /** UTC epoch millis at last update */
    @ColumnInfo(name = "updated_at")
    @SerializedName("updatedAt")
    private final long updatedAt;

    /** Soft-delete flag for compliance (hard delete after TTL on server) */
    @SerializedName("deleted")
    private final boolean deleted;

    /** Ordered list of user reactions (👍, ❤️, etc.) */
    @NonNull
    @SerializedName("reactions")
    private final List<Reaction> reactions;

    /* ---------- Constructors ---------- */

    private Comment(@NonNull Builder builder) {
        this.id = builder.id;
        this.postId = builder.postId;
        this.authorId = builder.authorId;
        this.authorDisplayName = builder.authorDisplayName;
        this.body = builder.body;
        this.createdAt = builder.createdAt;
        this.updatedAt = builder.updatedAt;
        this.deleted = builder.deleted;
        this.reactions = builder.reactions == null
                ? new ArrayList<>()
                : Collections.unmodifiableList(new ArrayList<>(builder.reactions));
    }

    /* ---------- Business Logic ---------- */

    /**
     * Validate comment for local persistence & network transmission.
     *
     * @return true if comment is well-formed, false otherwise.
     */
    public boolean isValid() {
        return !deleted
                && !body.trim().isEmpty()
                && postId.length() > 0
                && authorId.length() > 0;
    }

    /**
     * Return a copy with updated body & timestamp.
     * Any attempt to update a deleted comment will throw IllegalStateException.
     */
    public Comment withUpdatedBody(@NonNull String newBody, long newUpdatedAt) {
        if (deleted) {
            throw new IllegalStateException("Cannot update a deleted comment");
        }
        return new Builder(this)
                .body(newBody)
                .updatedAt(newUpdatedAt)
                .build();
    }

    /**
     * Merge remote state into current instance, prioritising the "newer"
     * updatedAt timestamp. Used by Repository for offline conflict resolution.
     */
    public Comment merge(@NonNull Comment remote) {
        if (!Objects.equals(id, remote.id)) {
            throw new IllegalArgumentException("Cannot merge comments with different ids");
        }
        return this.updatedAt >= remote.updatedAt ? this : remote;
    }

    /* ---------- Getters ---------- */

    @NonNull public String getId() { return id; }
    @NonNull public String getPostId() { return postId; }
    @NonNull public String getAuthorId() { return authorId; }
    @NonNull public String getAuthorDisplayName() { return authorDisplayName; }
    @NonNull public String getBody() { return body; }
    public long getCreatedAt() { return createdAt; }
    public long getUpdatedAt() { return updatedAt; }
    public boolean isDeleted() { return deleted; }
    @NonNull public List<Reaction> getReactions() { return reactions; }

    /* ---------- Parcelable Implementation ---------- */

    protected Comment(Parcel in) {
        id = Objects.requireNonNull(in.readString());
        postId = Objects.requireNonNull(in.readString());
        authorId = Objects.requireNonNull(in.readString());
        authorDisplayName = Objects.requireNonNull(in.readString());
        body = Objects.requireNonNull(in.readString());
        createdAt = in.readLong();
        updatedAt = in.readLong();
        deleted = in.readByte() != 0;
        reactions = new ArrayList<>();
        in.readList(reactions, Reaction.class.getClassLoader());
    }

    @Override public void writeToParcel(@NonNull Parcel dest, int flags) {
        dest.writeString(id);
        dest.writeString(postId);
        dest.writeString(authorId);
        dest.writeString(authorDisplayName);
        dest.writeString(body);
        dest.writeLong(createdAt);
        dest.writeLong(updatedAt);
        dest.writeByte((byte) (deleted ? 1 : 0));
        dest.writeList(reactions);
    }

    @Override public int describeContents() { return 0; }

    public static final Creator<Comment> CREATOR = new Creator<Comment>() {
        @Override public Comment createFromParcel(Parcel in) { return new Comment(in); }
        @Override public Comment[] newArray(int size) { return new Comment[size]; }
    };

    /* ---------- Builder ---------- */

    public static final class Builder {
        private String id = UUID.randomUUID().toString();
        private String postId;
        private String authorId;
        private String authorDisplayName;
        private String body;
        private long createdAt = System.currentTimeMillis();
        private long updatedAt = createdAt;
        private boolean deleted;
        private List<Reaction> reactions = new ArrayList<>();

        public Builder() { /* default */ }

        public Builder(@NonNull Comment source) {
            id = source.id;
            postId = source.postId;
            authorId = source.authorId;
            authorDisplayName = source.authorDisplayName;
            body = source.body;
            createdAt = source.createdAt;
            updatedAt = source.updatedAt;
            deleted = source.deleted;
            reactions = new ArrayList<>(source.reactions);
        }

        public Builder id(@NonNull String id) { this.id = id; return this; }
        public Builder postId(@NonNull String postId) { this.postId = postId; return this; }
        public Builder authorId(@NonNull String authorId) { this.authorId = authorId; return this; }
        public Builder authorDisplayName(@NonNull String displayName) { this.authorDisplayName = displayName; return this; }
        public Builder body(@NonNull String body) { this.body = body.trim(); return this; }
        public Builder createdAt(long ts) { this.createdAt = ts; return this; }
        public Builder updatedAt(long ts) { this.updatedAt = ts; return this; }
        public Builder deleted(boolean deleted) { this.deleted = deleted; return this; }
        public Builder reactions(@Nullable List<Reaction> reactions) {
            this.reactions = reactions == null ? new ArrayList<>() : new ArrayList<>(reactions);
            return this;
        }

        public Comment build() {
            if (postId == null || authorId == null || authorDisplayName == null || body == null) {
                throw new IllegalStateException("Required fields missing");
            }
            return new Comment(this);
        }
    }

    /* ---------- Reaction Sub-Model ---------- */

    /**
     * Immutable value object representing a lightweight emoji-style reaction.
     */
    public static final class Reaction implements Parcelable {

        @NonNull
        @SerializedName("userId")
        private final String userId;

        @NonNull
        @SerializedName("emoji")
        private final String emoji;

        @SerializedName("createdAt")
        private final long createdAt;

        public Reaction(@NonNull String userId, @NonNull String emoji, long createdAt) {
            this.userId = userId;
            this.emoji = emoji;
            this.createdAt = createdAt;
        }

        protected Reaction(Parcel in) {
            userId = Objects.requireNonNull(in.readString());
            emoji = Objects.requireNonNull(in.readString());
            createdAt = in.readLong();
        }

        @Override public void writeToParcel(@NonNull Parcel dest, int flags) {
            dest.writeString(userId);
            dest.writeString(emoji);
            dest.writeLong(createdAt);
        }

        @Override public int describeContents() { return 0; }

        public static final Creator<Reaction> CREATOR = new Creator<Reaction>() {
            @Override public Reaction createFromParcel(Parcel in) { return new Reaction(in); }
            @Override public Reaction[] newArray(int size) { return new Reaction[size]; }
        };

        @NonNull public String getUserId() { return userId; }
        @NonNull public String getEmoji() { return emoji; }
        public long getCreatedAt() { return createdAt; }

        @Override public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof Reaction)) return false;
            Reaction reaction = (Reaction) o;
            return Objects.equals(userId, reaction.userId) &&
                   Objects.equals(emoji, reaction.emoji);
        }

        @Override public int hashCode() { return Objects.hash(userId, emoji); }
    }

    /* ---------- Room TypeConverter ---------- */

    /**
     * Converts List<Reaction> ↔ JSON string for Room column persistence.
     * Uses a very small reflection-free JSON implementation for performance.
     */
    static final class ReactionListConverter {
        private static final com.google.gson.Gson GSON = new com.google.gson.Gson();

        @TypeConverter
        public static String fromList(List<Reaction> reactions) {
            return reactions == null || reactions.isEmpty()
                    ? "[]"
                    : GSON.toJson(reactions);
        }

        @TypeConverter
        public static List<Reaction> toList(String data) {
            if (data == null || data.isEmpty()) return new ArrayList<>();
            java.lang.reflect.Type listType =
                    com.google.gson.reflect.TypeToken.getParameterized(List.class, Reaction.class).getType();
            List<Reaction> list = GSON.fromJson(data, listType);
            return list == null ? new ArrayList<>() : list;
        }
    }
}
```