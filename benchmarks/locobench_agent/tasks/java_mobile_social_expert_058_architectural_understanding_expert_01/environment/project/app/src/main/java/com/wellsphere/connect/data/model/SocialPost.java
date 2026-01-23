package com.wellsphere.connect.data.model;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Domain model representing a social post as displayed in the WellSphere Connect feed.
 * <p>
 * This object is:
 * <ul>
 *     <li>Immutable – created through the {@link Builder}</li>
 *     <li>{@link Parcelable} – for efficient Android inter-process transfers</li>
 *     <li>{@link Serializable} – for potential Java serialization use-cases</li>
 * </ul>
 *
 * The model purposefully avoids any View-layer concern to preserve MVVM boundaries.
 */
@SuppressWarnings("unused")
public final class SocialPost implements Parcelable, Serializable, Comparable<SocialPost> {

    //region Gson / JSON fields
    @SerializedName("id")
    @NonNull
    private final String id;

    @SerializedName("author_id")
    @NonNull
    private final String authorId;

    @SerializedName("author_display_name")
    @NonNull
    private final String authorDisplayName;

    @SerializedName("created_at_epoch_millis")
    private final long createdAtMillis;

    @SerializedName("content_text")
    @Nullable
    private final String text;

    @SerializedName("attachments")
    @NonNull
    private final List<Attachment> attachments;

    @SerializedName("privacy_level")
    @NonNull
    private final Privacy privacy;

    @SerializedName("latitude")
    @Nullable
    private final Double latitude;

    @SerializedName("longitude")
    @Nullable
    private final Double longitude;

    @SerializedName("like_count")
    private final int likeCount;

    @SerializedName("comment_count")
    private final int commentCount;

    @SerializedName("liked_by_current_user")
    private final boolean likedByCurrentUser;

    @SerializedName("sync_status")
    @NonNull
    private final SyncStatus syncStatus;
    //endregion

    //region Constructor
    private SocialPost(Builder b) {
        this.id = b.id;
        this.authorId = b.authorId;
        this.authorDisplayName = b.authorDisplayName;
        this.createdAtMillis = b.createdAtMillis;
        this.text = b.text;
        this.attachments = Collections.unmodifiableList(new ArrayList<>(b.attachments));
        this.privacy = b.privacy;
        this.latitude = b.latitude;
        this.longitude = b.longitude;
        this.likeCount = b.likeCount;
        this.commentCount = b.commentCount;
        this.likedByCurrentUser = b.likedByCurrentUser;
        this.syncStatus = b.syncStatus;
    }
    //endregion

    //region Business helpers

    /**
     * Returns {@code true} if the given <code>userId</code> is the post author.
     */
    public boolean isOwnedBy(@Nullable String userId) {
        return userId != null && userId.equals(authorId);
    }

    /**
     * Convenience method for quickly checking if at least one attachment
     * of the provided {@link Attachment.Type} exists.
     */
    public boolean hasAttachmentOfType(@NonNull Attachment.Type type) {
        for (Attachment a : attachments) {
            if (a.getType() == type) return true;
        }
        return false;
    }

    /**
     * Returns <code>true</code> when the post is still awaiting upload or retry.
     */
    public boolean isPendingUpload() {
        return syncStatus == SyncStatus.PENDING || syncStatus == SyncStatus.FAILED;
    }
    //endregion

    //region Parcelable implementation
    protected SocialPost(Parcel in) {
        id = Objects.requireNonNull(in.readString());
        authorId = Objects.requireNonNull(in.readString());
        authorDisplayName = Objects.requireNonNull(in.readString());
        createdAtMillis = in.readLong();
        text = in.readString();
        attachments = new ArrayList<>();
        in.readTypedList(attachments, Attachment.CREATOR);
        privacy = Privacy.valueOf(Objects.requireNonNull(in.readString()));
        if (in.readByte() == 0) {
            latitude = null;
        } else {
            latitude = in.readDouble();
        }
        if (in.readByte() == 0) {
            longitude = null;
        } else {
            longitude = in.readDouble();
        }
        likeCount = in.readInt();
        commentCount = in.readInt();
        likedByCurrentUser = in.readByte() != 0;
        syncStatus = SyncStatus.valueOf(Objects.requireNonNull(in.readString()));
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeString(id);
        dest.writeString(authorId);
        dest.writeString(authorDisplayName);
        dest.writeLong(createdAtMillis);
        dest.writeString(text);
        dest.writeTypedList(attachments);
        dest.writeString(privacy.name());
        if (latitude == null) {
            dest.writeByte((byte) 0);
        } else {
            dest.writeByte((byte) 1);
            dest.writeDouble(latitude);
        }
        if (longitude == null) {
            dest.writeByte((byte) 0);
        } else {
            dest.writeByte((byte) 1);
            dest.writeDouble(longitude);
        }
        dest.writeInt(likeCount);
        dest.writeInt(commentCount);
        dest.writeByte((byte) (likedByCurrentUser ? 1 : 0));
        dest.writeString(syncStatus.name());
    }

    @Override
    public int describeContents() {
        return 0;
    }

    public static final Creator<SocialPost> CREATOR = new Creator<SocialPost>() {
        @Override
        public SocialPost createFromParcel(Parcel in) {
            return new SocialPost(in);
        }

        @Override
        public SocialPost[] newArray(int size) {
            return new SocialPost[size];
        }
    };
    //endregion

    //region Getters
    @NonNull
    public String getId() { return id; }

    @NonNull
    public String getAuthorId() { return authorId; }

    @NonNull
    public String getAuthorDisplayName() { return authorDisplayName; }

    public long getCreatedAtMillis() { return createdAtMillis; }

    @Nullable
    public String getText() { return text; }

    @NonNull
    public List<Attachment> getAttachments() { return attachments; }

    @NonNull
    public Privacy getPrivacy() { return privacy; }

    @Nullable
    public Double getLatitude() { return latitude; }

    @Nullable
    public Double getLongitude() { return longitude; }

    public int getLikeCount() { return likeCount; }

    public int getCommentCount() { return commentCount; }

    public boolean isLikedByCurrentUser() { return likedByCurrentUser; }

    @NonNull
    public SyncStatus getSyncStatus() { return syncStatus; }
    //endregion

    //region Builder
    public static class Builder {
        private String id;
        private String authorId;
        private String authorDisplayName;
        private long createdAtMillis;
        private String text;
        private List<Attachment> attachments = new ArrayList<>();
        private Privacy privacy = Privacy.PUBLIC;
        private Double latitude;
        private Double longitude;
        private int likeCount;
        private int commentCount;
        private boolean likedByCurrentUser;
        private SyncStatus syncStatus = SyncStatus.SYNCED;

        public Builder(@NonNull String id) {
            this.id = Objects.requireNonNull(id, "id == null");
        }

        @NonNull
        public Builder author(@NonNull String authorId, @NonNull String displayName) {
            this.authorId = Objects.requireNonNull(authorId, "authorId == null");
            this.authorDisplayName = Objects.requireNonNull(displayName, "displayName == null");
            return this;
        }

        @NonNull
        public Builder createdAtMillis(long millis) {
            this.createdAtMillis = millis;
            return this;
        }

        @NonNull
        public Builder text(@Nullable String text) {
            this.text = text;
            return this;
        }

        @NonNull
        public Builder addAttachment(@NonNull Attachment a) {
            attachments.add(Objects.requireNonNull(a, "attachment == null"));
            return this;
        }

        @NonNull
        public Builder attachments(@NonNull List<Attachment> list) {
            this.attachments = new ArrayList<>(Objects.requireNonNull(list, "attachments == null"));
            return this;
        }

        @NonNull
        public Builder privacy(@NonNull Privacy p) {
            this.privacy = Objects.requireNonNull(p, "privacy == null");
            return this;
        }

        @NonNull
        public Builder location(@Nullable Double lat, @Nullable Double lon) {
            this.latitude = lat;
            this.longitude = lon;
            return this;
        }

        @NonNull
        public Builder likeInfo(int count, boolean likedByMe) {
            this.likeCount = count;
            this.likedByCurrentUser = likedByMe;
            return this;
        }

        @NonNull
        public Builder commentCount(int count) {
            this.commentCount = count;
            return this;
        }

        @NonNull
        public Builder syncStatus(@NonNull SyncStatus status) {
            this.syncStatus = Objects.requireNonNull(status, "syncStatus == null");
            return this;
        }

        public SocialPost build() {
            // Basic validation
            if (authorId == null || authorDisplayName == null) {
                throw new IllegalStateException("Author information must be provided");
            }
            if (createdAtMillis <= 0) {
                createdAtMillis = System.currentTimeMillis();
            }
            return new SocialPost(this);
        }
    }
    //endregion

    //region Enums
    /**
     * HIPAA-aware privacy levels applied to the post.
     */
    public enum Privacy {
        PUBLIC,
        CARE_TEAM,   // Visible to linked clinicians
        PRIVATE      // Visible only to the author
    }

    /**
     * Local-DB sync state
     */
    public enum SyncStatus {
        SYNCED,
        PENDING,
        FAILED
    }
    //endregion

    //region Attachment inner-class
    /**
     * Lightweight description of a media or document attached to a post.
     */
    public static class Attachment implements Parcelable, Serializable {

        @SerializedName("uri")
        @NonNull
        private final String uri;

        @SerializedName("type")
        @NonNull
        private final Type type;

        @SerializedName("thumbnail_uri")
        @Nullable
        private final String thumbnailUri;

        @SerializedName("width")
        private final int width;

        @SerializedName("height")
        private final int height;

        private Attachment(Builder builder) {
            this.uri = builder.uri;
            this.type = builder.type;
            this.thumbnailUri = builder.thumbnailUri;
            this.width = builder.width;
            this.height = builder.height;
        }

        protected Attachment(Parcel in) {
            uri = Objects.requireNonNull(in.readString());
            type = Type.valueOf(Objects.requireNonNull(in.readString()));
            thumbnailUri = in.readString();
            width = in.readInt();
            height = in.readInt();
        }

        @Override
        public void writeToParcel(Parcel dest, int flags) {
            dest.writeString(uri);
            dest.writeString(type.name());
            dest.writeString(thumbnailUri);
            dest.writeInt(width);
            dest.writeInt(height);
        }

        @Override
        public int describeContents() {
            return 0;
        }

        public static final Creator<Attachment> CREATOR = new Creator<Attachment>() {
            @Override
            public Attachment createFromParcel(Parcel in) {
                return new Attachment(in);
            }

            @Override
            public Attachment[] newArray(int size) {
                return new Attachment[size];
            }
        };

        //region Getters
        @NonNull
        public String getUri() { return uri; }

        @NonNull
        public Type getType() { return type; }

        @Nullable
        public String getThumbnailUri() { return thumbnailUri; }

        public int getWidth() { return width; }

        public int getHeight() { return height; }
        //endregion

        //region Builder
        public static class Builder {
            private String uri;
            private Type type;
            private String thumbnailUri;
            private int width;
            private int height;

            public Builder(@NonNull String uri, @NonNull Type type) {
                this.uri = Objects.requireNonNull(uri, "uri == null");
                this.type = Objects.requireNonNull(type, "type == null");
            }

            @NonNull
            public Builder thumbnail(@Nullable String thumbnailUri) {
                this.thumbnailUri = thumbnailUri;
                return this;
            }

            @NonNull
            public Builder dimensions(int width, int height) {
                this.width = width;
                this.height = height;
                return this;
            }

            public Attachment build() {
                return new Attachment(this);
            }
        }
        //endregion

        public enum Type {
            IMAGE,
            VIDEO,
            DOCUMENT
        }
    }
    //endregion

    //region Comparable, equals, hashCode, toString
    @Override
    public int compareTo(@NonNull SocialPost o) {
        return Long.compare(o.createdAtMillis, createdAtMillis); // Newest first
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof SocialPost)) return false;
        SocialPost that = (SocialPost) o;
        return id.equals(that.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }

    @Override
    public String toString() {
        return "SocialPost{" +
                "id='" + id + '\'' +
                ", authorId='" + authorId + '\'' +
                ", createdAtMillis=" + createdAtMillis +
                ", text='" + text + '\'' +
                ", attachments=" + attachments.size() +
                ", privacy=" + privacy +
                '}';
    }
    //endregion

    //region JSON convenience
    /**
     * Serializes this post using the provided {@link Gson} instance.
     */
    public String toJson(@NonNull Gson gson) {
        return gson.toJson(this);
    }

    /**
     * Deserializes a {@link SocialPost} from JSON.
     *
     * @throws IllegalArgumentException when JSON cannot be parsed or is invalid
     */
    public static SocialPost fromJson(@NonNull Gson gson, @NonNull String json) {
        try {
            return gson.fromJson(json, SocialPost.class);
        } catch (Exception ex) {
            throw new IllegalArgumentException("Failed to parse SocialPost JSON", ex);
        }
    }
    //endregion
}