package com.wellsphere.connect.data.model;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.ColumnInfo;
import androidx.room.Entity;
import androidx.room.Ignore;
import androidx.room.PrimaryKey;
import androidx.room.TypeConverter;
import androidx.room.TypeConverters;

import com.google.gson.annotations.SerializedName;

import java.io.Serializable;
import java.util.Calendar;
import java.util.Date;
import java.util.Objects;

/**
 * Domain + Room entity that represents a single medication row.
 * <p>
 * It is serialisable via {@link Parcelable} for inter–component transport,
 * GSON-friendly through {@link SerializedName}, and Room-ready via standard
 * annotations.  All instances MUST be created through {@link Builder} to
 * guarantee validation and forward-compatibility.
 */
@Entity(tableName = "medications")
@TypeConverters(Medication.Converters.class)
public class Medication implements Parcelable, Serializable {

    // region Room columns -----------------------------------------------------------------------

    @PrimaryKey(autoGenerate = true)
    @ColumnInfo(name = "id")
    @SerializedName("local_id")
    private long id;

    /**
     * Optional server-side UUID.  May be {@code null} when record has not
     * yet been pushed to the cloud.
     */
    @ColumnInfo(name = "remote_id")
    @SerializedName("medication_id")
    @Nullable
    private String remoteId;

    @NonNull
    @ColumnInfo(name = "name")
    @SerializedName("name")
    private String name;

    @NonNull
    @ColumnInfo(name = "dosage")
    @SerializedName("dosage")
    private String dosage;

    @NonNull
    @ColumnInfo(name = "frequency")
    @SerializedName("frequency")
    private String frequency;

    @ColumnInfo(name = "start_date")
    @SerializedName("start_date")
    @Nullable
    private Date startDate;

    @ColumnInfo(name = "end_date")
    @SerializedName("end_date")
    @Nullable
    private Date endDate;

    @ColumnInfo(name = "is_prn")
    @SerializedName("is_prn")
    private boolean prn;

    @ColumnInfo(name = "is_deleted")
    @SerializedName("deleted")
    private boolean deleted;

    @ColumnInfo(name = "updated_at")
    @SerializedName("last_modified")
    @Nullable
    private Date updatedAt;

    // endregion

    // region Constructors -----------------------------------------------------------------------

    /**
     * Full constructor required by Room.  Keep package-private.
     */
    Medication(long id,
               @Nullable String remoteId,
               @NonNull String name,
               @NonNull String dosage,
               @NonNull String frequency,
               @Nullable Date startDate,
               @Nullable Date endDate,
               boolean prn,
               boolean deleted,
               @Nullable Date updatedAt) {
        this.id = id;
        this.remoteId = remoteId;
        this.name = name;
        this.dosage = dosage;
        this.frequency = frequency;
        this.startDate = startDate;
        this.endDate = endDate;
        this.prn = prn;
        this.deleted = deleted;
        this.updatedAt = updatedAt;
    }

    /**
     * Convenience constructor used exclusively by {@link Builder}.
     */
    @Ignore
    private Medication(Builder builder) {
        this(builder.id,
             builder.remoteId,
             builder.name,
             builder.dosage,
             builder.frequency,
             builder.startDate,
             builder.endDate,
             builder.prn,
             builder.deleted,
             builder.updatedAt);
    }

    // endregion

    // region Business logic ---------------------------------------------------------------------

    /**
     * Returns {@code true} if the medication is considered active on the
     * specified calendar day.
     *
     * @param day The day to test against.  Uses current day if {@code null}.
     */
    public boolean isActive(@Nullable Calendar day) {
        Calendar target = day != null ? day : Calendar.getInstance();

        // Guard against open-ended schedules.
        if (startDate == null && endDate == null) return true;

        if (startDate != null && target.before(toCalendar(startDate))) return false;
        if (endDate != null && target.after(toCalendar(endDate))) return false;
        return true;
    }

    private static Calendar toCalendar(@NonNull Date date) {
        Calendar c = Calendar.getInstance();
        c.setTime(date);
        return c;
    }

    /**
     * Returns true when the object has been synced with the backend.
     */
    public boolean isSynced() {
        return remoteId != null && !remoteId.isEmpty();
    }

    /**
     * Marks the entity as deleted.  Actual removal is executed by the sync
     * engine once the backend acknowledges the tombstone.
     */
    public void softDelete() {
        this.deleted = true;
        this.updatedAt = new Date();
    }

    // endregion

    // region Getters & Setters ------------------------------------------------------------------

    public long getId() {
        return id;
    }

    @Nullable
    public String getRemoteId() {
        return remoteId;
    }

    @NonNull
    public String getName() {
        return name;
    }

    @NonNull
    public String getDosage() {
        return dosage;
    }

    @NonNull
    public String getFrequency() {
        return frequency;
    }

    @Nullable
    public Date getStartDate() {
        return startDate;
    }

    @Nullable
    public Date getEndDate() {
        return endDate;
    }

    public boolean isPrn() {
        return prn;
    }

    public boolean isDeleted() {
        return deleted;
    }

    @Nullable
    public Date getUpdatedAt() {
        return updatedAt;
    }

    // endregion

    // region Parcelable implementation ----------------------------------------------------------

    protected Medication(Parcel in) {
        id = in.readLong();
        remoteId = in.readString();
        name = Objects.requireNonNull(in.readString());
        dosage = Objects.requireNonNull(in.readString());
        frequency = Objects.requireNonNull(in.readString());
        startDate = readDate(in);
        endDate = readDate(in);
        prn = in.readByte() != 0;
        deleted = in.readByte() != 0;
        updatedAt = readDate(in);
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeLong(id);
        dest.writeString(remoteId);
        dest.writeString(name);
        dest.writeString(dosage);
        dest.writeString(frequency);
        writeDate(dest, startDate);
        writeDate(dest, endDate);
        dest.writeByte((byte) (prn ? 1 : 0));
        dest.writeByte((byte) (deleted ? 1 : 0));
        writeDate(dest, updatedAt);
    }

    @Override
    public int describeContents() {
        return 0;
    }

    private static Date readDate(Parcel in) {
        long tmp = in.readLong();
        return tmp == -1L ? null : new Date(tmp);
    }

    private static void writeDate(Parcel dest, @Nullable Date date) {
        dest.writeLong(date != null ? date.getTime() : -1L);
    }

    public static final Creator<Medication> CREATOR = new Creator<Medication>() {
        @Override
        public Medication createFromParcel(Parcel in) {
            return new Medication(in);
        }

        @Override
        public Medication[] newArray(int size) {
            return new Medication[size];
        }
    };

    // endregion

    // region Equality ---------------------------------------------------------------------------

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Medication)) return false;
        Medication that = (Medication) o;
        return id == that.id
                && prn == that.prn
                && deleted == that.deleted
                && Objects.equals(remoteId, that.remoteId)
                && name.equals(that.name)
                && dosage.equals(that.dosage)
                && frequency.equals(that.frequency)
                && Objects.equals(startDate, that.startDate)
                && Objects.equals(endDate, that.endDate)
                && Objects.equals(updatedAt, that.updatedAt);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, remoteId, name, dosage, frequency,
                startDate, endDate, prn, deleted, updatedAt);
    }

    @Override
    public String toString() {
        return "Medication{" +
                "id=" + id +
                ", remoteId='" + remoteId + '\'' +
                ", name='" + name + '\'' +
                ", dosage='" + dosage + '\'' +
                ", frequency='" + frequency + '\'' +
                ", startDate=" + startDate +
                ", endDate=" + endDate +
                ", prn=" + prn +
                ", deleted=" + deleted +
                ", updatedAt=" + updatedAt +
                '}';
    }

    // endregion

    // region Builder ----------------------------------------------------------------------------

    public static class Builder {

        private long id;
        private String remoteId;
        private String name;
        private String dosage;
        private String frequency;
        private Date startDate;
        private Date endDate;
        private boolean prn;
        private boolean deleted;
        private Date updatedAt;

        public Builder() {
            // Default sensible values
            this.name = "";
            this.dosage = "";
            this.frequency = "";
            this.updatedAt = new Date();
        }

        public Builder setId(long id) {
            this.id = id;
            return this;
        }

        public Builder setRemoteId(@Nullable String remoteId) {
            this.remoteId = remoteId;
            return this;
        }

        public Builder setName(@NonNull String name) {
            this.name = name;
            return this;
        }

        public Builder setDosage(@NonNull String dosage) {
            this.dosage = dosage;
            return this;
        }

        public Builder setFrequency(@NonNull String frequency) {
            this.frequency = frequency;
            return this;
        }

        public Builder setStartDate(@Nullable Date startDate) {
            this.startDate = startDate;
            return this;
        }

        public Builder setEndDate(@Nullable Date endDate) {
            this.endDate = endDate;
            return this;
        }

        public Builder setPrn(boolean prn) {
            this.prn = prn;
            return this;
        }

        public Builder setDeleted(boolean deleted) {
            this.deleted = deleted;
            return this;
        }

        public Builder setUpdatedAt(@Nullable Date updatedAt) {
            this.updatedAt = updatedAt;
            return this;
        }

        /**
         * Performs defensive checks before constructing immutable entity.
         *
         * @throws IllegalStateException when required fields are missing
         *                               or invalid.
         */
        public Medication build() {
            if (name == null || name.trim().isEmpty()) {
                throw new IllegalStateException("Medication name must not be empty");
            }
            if (dosage == null || dosage.trim().isEmpty()) {
                throw new IllegalStateException("Dosage must not be empty");
            }
            if (frequency == null || frequency.trim().isEmpty()) {
                throw new IllegalStateException("Frequency must not be empty");
            }
            if (startDate != null && endDate != null && startDate.after(endDate)) {
                throw new IllegalStateException("Start date must be before end date");
            }

            // If updatedAt not provided, use now.
            if (updatedAt == null) {
                updatedAt = new Date();
            }

            return new Medication(this);
        }
    }

    // endregion

    // region TypeConverters ---------------------------------------------------------------------

    /**
     * Room {@link TypeConverter}s for java.util.Date.
     */
    public static class Converters {

        @TypeConverter
        public static Long fromDate(@Nullable Date date) {
            return date != null ? date.getTime() : null;
        }

        @TypeConverter
        public static Date toDate(@Nullable Long millis) {
            return millis != null ? new Date(millis) : null;
        }
    }

    // endregion
}