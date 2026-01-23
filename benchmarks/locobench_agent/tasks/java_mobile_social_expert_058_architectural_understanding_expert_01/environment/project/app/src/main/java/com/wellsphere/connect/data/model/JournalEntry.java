```java
/*
 * WellSphere Connect
 * Copyright (c) 2024  WellSphere
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.wellsphere.connect.data.model;

import android.net.Uri;
import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.ColumnInfo;
import androidx.room.Entity;
import androidx.room.PrimaryKey;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

/**
 * JournalEntry represents a single line item in a user’s longitudinal health journal.
 * <p>
 * The class is intentionally immutable in order to guarantee thread-safety when it’s passed
 * between background services (e.g. biometric authentication service, crash reporter, sync
 * service) and UI components (e.g. ViewModels, adapters).  Use {@link Builder} to create a new
 * instance or mutate an existing instance.
 * <p>
 * The object is also annotated as a Room entity for local persistence and implements Parcelable
 * so that it can be transported via Android IPC (e.g. intents, saved-instance-state).
 */
@Entity(tableName = "journal_entries")
public final class JournalEntry implements Parcelable {

    //region Entity fields
    @PrimaryKey
    @NonNull
    @ColumnInfo(name = "entry_id")
    @SerializedName("id")
    private final String id;

    @NonNull
    @ColumnInfo(name = "user_id", index = true)
    @SerializedName("userId")
    private final String userId;

    @NonNull
    @ColumnInfo(name = "created_at")
    @SerializedName("createdAt")
    private final Date createdAt;

    @NonNull
    @ColumnInfo(name = "mood")
    @SerializedName("mood")
    private final Mood mood;

    @Nullable
    @ColumnInfo(name = "notes")
    @SerializedName("notes")
    private final String notes;

    @NonNull
    @ColumnInfo(name = "tags")
    @SerializedName("tags")
    private final List<String> tags;

    @NonNull
    @ColumnInfo(name = "attachments")
    @SerializedName("attachments")
    private final List<Attachment> attachments;

    @Nullable
    @ColumnInfo(name = "latitude")
    @SerializedName("latitude")
    private final Double latitude;

    @Nullable
    @ColumnInfo(name = "longitude")
    @SerializedName("longitude")
    private final Double longitude;

    @NonNull
    @ColumnInfo(name = "privacy_level")
    @SerializedName("privacyLevel")
    private final PrivacyLevel privacyLevel;

    @ColumnInfo(name = "synced")
    @SerializedName("synced")
    private final boolean synced;
    //endregion

    //region Constructor
    private JournalEntry(@NonNull Builder builder) {
        this.id = builder.id;
        this.userId = builder.userId;
        this.createdAt = builder.createdAt;
        this.mood = builder.mood;
        this.notes = builder.notes;
        this.tags = Collections.unmodifiableList(builder.tags);
        this.attachments = Collections.unmodifiableList(builder.attachments);
        this.latitude = builder.latitude;
        this.longitude = builder.longitude;
        this.privacyLevel = builder.privacyLevel;
        this.synced = builder.synced;
    }
    //endregion

    //region Parcelable
    protected JournalEntry(Parcel in) {
        id = Objects.requireNonNull(in.readString());
        userId = Objects.requireNonNull(in.readString());
        createdAt = new Date(in.readLong());
        mood = Mood.valueOf(in.readString());
        notes = in.readString();
        tags = new ArrayList<>();
        in.readStringList(tags);
        attachments = new ArrayList<>();
        in.readTypedList(attachments, Attachment.CREATOR);
        latitude = in.readByte() == 0 ? null : in.readDouble();
        longitude = in.readByte() == 0 ? null : in.readDouble();
        privacyLevel = PrivacyLevel.valueOf(in.readString());
        synced = in.readByte() != 0;
    }

    @Override
    public void writeToParcel(@NonNull Parcel dest, int flags) {
        dest.writeString(id);
        dest.writeString(userId);
        dest.writeLong(createdAt.getTime());
        dest.writeString(mood.name());
        dest.writeString(notes);
        dest.writeStringList(tags);
        dest.writeTypedList(attachments);
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
        dest.writeString(privacyLevel.name());
        dest.writeByte((byte) (synced ? 1 : 0));
    }

    @Override
    public int describeContents() {
        return 0;
    }

    public static final Creator<JournalEntry> CREATOR = new Creator<JournalEntry>() {
        @Override
        public JournalEntry createFromParcel(Parcel in) {
            return new JournalEntry(in);
        }

        @Override
        public JournalEntry[] newArray(int size) {
            return new JournalEntry[size];
        }
    };
    //endregion

    //region Getters
    @NonNull public String getId() { return id; }
    @NonNull public String getUserId() { return userId; }
    @NonNull public Date getCreatedAt() { return new Date(createdAt.getTime()); }
    @NonNull public Mood getMood() { return mood; }
    @Nullable public String getNotes() { return notes; }
    @NonNull public List<String> getTags() { return tags; }
    @NonNull public List<Attachment> getAttachments() { return attachments; }
    @Nullable public Double getLatitude() { return latitude; }
    @Nullable public Double getLongitude() { return longitude; }
    @NonNull public PrivacyLevel getPrivacyLevel() { return privacyLevel; }
    public boolean isSynced() { return synced; }
    //endregion

    //region Serialization helpers
    /**
     * Serialize a JournalEntry to its JSON representation.
     * Note: Gson is thread-safe, so a shared instance is acceptable here.
     */
    @NonNull
    public String toJson() {
        return GsonHolder.GSON.toJson(this);
    }

    /**
     * Parse JSON into a JournalEntry.  If the JSON is malformed or does not adhere to the model’s
     * schema, an {@link IllegalArgumentException} is thrown.
     */
    @NonNull
    public static JournalEntry fromJson(@NonNull String json) {
        JournalEntry entry = GsonHolder.GSON.fromJson(json, JournalEntry.class);
        if (entry == null) {
            // Should never happen but keep guard for nulls coming from Gson
            throw new IllegalArgumentException("Unable to deserialize JournalEntry: JSON was null.");
        }
        entry.validate();
        return entry;
    }
    //endregion

    //region Validation
    /**
     * Perform a quick validity check.  This is called automatically by the builder
     * but can also be invoked after deserialization from JSON.
     */
    public void validate() {
        // Simple business rules
        if (userId.trim().isEmpty()) {
            throw new IllegalStateException("JournalEntry must contain a non-empty userId.");
        }
        if (createdAt.after(new Date())) {
            throw new IllegalStateException("JournalEntry cannot have a future createdAt date.");
        }
        if (latitude != null && (latitude < -90 || latitude > 90)) {
            throw new IllegalStateException("Latitude must be between -90 and 90.");
        }
        if (longitude != null && (longitude < -180 || longitude > 180)) {
            throw new IllegalStateException("Longitude must be between -180 and 180.");
        }
    }
    //endregion

    //region Equality & hashing
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof JournalEntry)) return false;
        JournalEntry that = (JournalEntry) o;
        return id.equals(that.id);
    }

    @Override
    public int hashCode() {
        return id.hashCode();
    }
    //endregion

    //region Builder
    public static final class Builder {
        private final String id;
        private final String userId;
        private final Date createdAt;

        private Mood mood = Mood.UNSPECIFIED;
        private String notes;
        private List<String> tags = new ArrayList<>();
        private List<Attachment> attachments = new ArrayList<>();
        private Double latitude;
        private Double longitude;
        private PrivacyLevel privacyLevel = PrivacyLevel.CARE_TEAM;
        private boolean synced = false;

        /**
         * Create a new builder.  For a brand-new entry use {@link #createNew(String)} which will
         * auto-generate the id and timestamp.  Use this constructor when you already have a
         * canonical identifier and timestamp (e.g. coming from server).
         */
        public Builder(@NonNull String id, @NonNull String userId, @NonNull Date createdAt) {
            this.id = Objects.requireNonNull(id);
            this.userId = Objects.requireNonNull(userId);
            this.createdAt = new Date(createdAt.getTime());
        }

        /**
         * Convenience factory for creating a builder for a new entry generated on-device.
         */
        public static Builder createNew(@NonNull String userId) {
            return new Builder(UUID.randomUUID().toString(), userId, new Date());
        }

        public Builder mood(@NonNull Mood mood) {
            this.mood = Objects.requireNonNull(mood);
            return this;
        }

        public Builder notes(@Nullable String notes) {
            this.notes = notes;
            return this;
        }

        public Builder tags(@NonNull List<String> tags) {
            this.tags = new ArrayList<>(Objects.requireNonNull(tags));
            return this;
        }

        public Builder addTag(@NonNull String tag) {
            if (!this.tags.contains(tag)) {
                this.tags.add(tag);
            }
            return this;
        }

        public Builder attachments(@NonNull List<Attachment> attachments) {
            this.attachments = new ArrayList<>(Objects.requireNonNull(attachments));
            return this;
        }

        public Builder addAttachment(@NonNull Attachment attachment) {
            this.attachments.add(Objects.requireNonNull(attachment));
            return this;
        }

        public Builder location(@Nullable Double latitude, @Nullable Double longitude) {
            this.latitude = latitude;
            this.longitude = longitude;
            return this;
        }

        public Builder privacyLevel(@NonNull PrivacyLevel level) {
            this.privacyLevel = Objects.requireNonNull(level);
            return this;
        }

        public Builder synced(boolean synced) {
            this.synced = synced;
            return this;
        }

        /**
         * Build the immutable JournalEntry instance.
         *
         * @throws IllegalStateException when validation fails
         */
        @NonNull
        public JournalEntry build() {
            JournalEntry entry = new JournalEntry(this);
            entry.validate();
            return entry;
        }
    }
    //endregion

    //region Nested types
    /**
     * Enum representing coarse mood categories for quick emotional check-ins.
     */
    public enum Mood {
        UNSPECIFIED,
        HAPPY,
        NEUTRAL,
        SAD,
        PAIN,
        ANXIOUS,
        ANGRY
    }

    /**
     * Enum describing who can see the entry:
     *  - PUBLIC: Visible to community feeds
     *  - CARE_TEAM: Only visible to patient and linked clinicians
     *  - PRIVATE: Only visible on the device, never synced to cloud
     */
    public enum PrivacyLevel {
        PUBLIC,
        CARE_TEAM,
        PRIVATE
    }

    /**
     * Simple attachment descriptor.  Only the Uri is stored here.
     */
    public static class Attachment implements Parcelable {

        @NonNull
        @SerializedName("uri")
        private final Uri uri;

        @NonNull
        @SerializedName("mimeType")
        private final String mimeType;

        public Attachment(@NonNull Uri uri, @NonNull String mimeType) {
            this.uri = uri;
            this.mimeType = mimeType;
        }

        protected Attachment(Parcel in) {
            uri = Objects.requireNonNull(in.readParcelable(Uri.class.getClassLoader()));
            mimeType = Objects.requireNonNull(in.readString());
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

        @Override public int describeContents() { return 0; }

        @Override
        public void writeToParcel(@NonNull Parcel dest, int flags) {
            dest.writeParcelable(uri, flags);
            dest.writeString(mimeType);
        }

        @NonNull public Uri getUri() { return uri; }
        @NonNull public String getMimeType() { return mimeType; }

        @Override public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof Attachment)) return false;
            Attachment that = (Attachment) o;
            return uri.equals(that.uri);
        }

        @Override public int hashCode() {
            return uri.hashCode();
        }
    }
    //endregion

    //region Gson Holder
    /**
     * Holder class for a lazily-initialised, thread-safe singleton Gson instance.
     * Using Holder pattern avoids the overhead of synchronization.
     */
    private static final class GsonHolder {
        private static final Gson GSON = new Gson();
    }
    //endregion
}
```