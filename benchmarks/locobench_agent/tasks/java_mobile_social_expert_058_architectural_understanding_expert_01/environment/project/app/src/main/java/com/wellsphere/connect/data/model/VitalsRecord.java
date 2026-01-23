package com.wellsphere.connect.data.model;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.ColumnInfo;
import androidx.room.Entity;
import androidx.room.PrimaryKey;
import androidx.room.TypeConverter;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;

import java.io.Serializable;
import java.util.Objects;
import java.util.UUID;

/**
 * Immutable representation of a single vital-sign measurement recorded by the user.
 *
 * Design notes:
 * • Acts as a Room entity (local persistence), Moshi model (JSON-serialization) and Parcelable
 *   (IPC / Bundle transfer) simultaneously.
 * • Records may carry either a numericValue or a stringValue (e.g. “120/80” for blood pressure);
 *   at least one must be present.
 * • Validation rules are enforced in the Builder to guarantee that invalid records cannot be
 *   constructed.
 */
@SuppressWarnings("WeakerAccess")
@JsonClass(generateAdapter = true)
@Entity(tableName = "vitals_records")
public final class VitalsRecord implements Parcelable, Serializable {

    private static final long serialVersionUID = 42L;

    // ------------------------
    // Room-backed primary key
    // ------------------------
    @PrimaryKey
    @NonNull
    @Json(name = "id")
    private final String id;

    // ------------------------
    // Foreign key -> owning user
    // ------------------------
    @NonNull
    @ColumnInfo(name = "user_id")
    @Json(name = "userId")
    private final String userId;

    // ------------------------
    // Type of vital being recorded (heart rate, weight, …)
    // ------------------------
    @NonNull
    @ColumnInfo(name = "type")
    @Json(name = "type")
    private final VitalType type;

    // ------------------------
    // Numeric value — if applicable
    // ------------------------
    @Nullable
    @ColumnInfo(name = "numeric_value")
    @Json(name = "numericValue")
    private final Double numericValue;

    // ------------------------
    // String value — alternative to numericValue (e.g. "120/80")
    // ------------------------
    @Nullable
    @ColumnInfo(name = "string_value")
    @Json(name = "stringValue")
    private final String stringValue;

    // ------------------------
    // Display / unit string (e.g. "bpm", "mg/dL")
    // ------------------------
    @Nullable
    @ColumnInfo(name = "unit")
    @Json(name = "unit")
    private final String unit;

    // ------------------------
    // Epoch-millis timestamp when the value was measured (not when uploaded)
    // ------------------------
    @ColumnInfo(name = "recorded_at")
    @Json(name = "recordedAt")
    private final long recordedAt;

    // ------------------------
    // Synchronisation state with remote backend
    // ------------------------
    @ColumnInfo(name = "synced")
    @Json(name = "synced")
    private final boolean synced;

    // ------------------------
    // Optional client-side note attached by the user
    // ------------------------
    @Nullable
    @ColumnInfo(name = "note")
    @Json(name = "note")
    private final String note;

    // ------------------------
    // Private constructor -> use Builder
    // ------------------------
    private VitalsRecord(Builder builder) {
        id = builder.id;
        userId = builder.userId;
        type = builder.type;
        numericValue = builder.numericValue;
        stringValue = builder.stringValue;
        unit = builder.unit;
        recordedAt = builder.recordedAt;
        synced = builder.synced;
        note = builder.note;
    }

    // -------------------------------------
    // Factory-style builder with validation
    // -------------------------------------
    public static final class Builder {
        private String id = UUID.randomUUID().toString();
        private String userId;
        private VitalType type;
        private Double numericValue;
        private String stringValue;
        private String unit;
        private long recordedAt = System.currentTimeMillis();
        private boolean synced = false;
        private String note;

        public Builder(@NonNull String userId, @NonNull VitalType type) {
            this.userId = Objects.requireNonNull(userId, "userId == null");
            this.type = Objects.requireNonNull(type, "type == null");
        }

        public Builder id(@NonNull String id) {
            this.id = Objects.requireNonNull(id, "id == null");
            return this;
        }

        public Builder numericValue(@Nullable Double numericValue) {
            this.numericValue = numericValue;
            return this;
        }

        public Builder stringValue(@Nullable String stringValue) {
            this.stringValue = stringValue;
            return this;
        }

        public Builder unit(@Nullable String unit) {
            this.unit = unit;
            return this;
        }

        public Builder recordedAt(long epochMillis) {
            this.recordedAt = epochMillis;
            return this;
        }

        public Builder synced(boolean synced) {
            this.synced = synced;
            return this;
        }

        public Builder note(@Nullable String note) {
            this.note = note;
            return this;
        }

        public VitalsRecord build() {
            // --------------------------
            // Business-rule validations
            // --------------------------
            if (numericValue == null && (stringValue == null || stringValue.trim().isEmpty())) {
                throw new IllegalStateException(
                        "Either numericValue or stringValue must be supplied");
            }

            if (numericValue != null) {
                if (numericValue.isNaN() || numericValue.isInfinite() || numericValue < 0) {
                    throw new IllegalArgumentException("numericValue is invalid: " + numericValue);
                }
            }

            return new VitalsRecord(this);
        }
    }

    // -------------------------------------
    // Parcelable impl  (keep in sync w/↑)
    // -------------------------------------
    protected VitalsRecord(Parcel in) {
        id = Objects.requireNonNull(in.readString());
        userId = Objects.requireNonNull(in.readString());
        type = VitalType.valueOf(Objects.requireNonNull(in.readString()));
        if (in.readByte() == 0) {
            numericValue = null;
        } else {
            numericValue = in.readDouble();
        }
        stringValue = in.readString();
        unit = in.readString();
        recordedAt = in.readLong();
        synced = in.readByte() != 0;
        note = in.readString();
    }

    public static final Creator<VitalsRecord> CREATOR = new Creator<VitalsRecord>() {
        @Override
        public VitalsRecord createFromParcel(Parcel in) {
            return new VitalsRecord(in);
        }

        @Override
        public VitalsRecord[] newArray(int size) {
            return new VitalsRecord[size];
        }
    };

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeString(id);
        dest.writeString(userId);
        dest.writeString(type.name());
        if (numericValue == null) {
            dest.writeByte((byte) 0);
        } else {
            dest.writeByte((byte) 1);
            dest.writeDouble(numericValue);
        }
        dest.writeString(stringValue);
        dest.writeString(unit);
        dest.writeLong(recordedAt);
        dest.writeByte((byte) (synced ? 1 : 0));
        dest.writeString(note);
    }

    @Override
    public int describeContents() {
        return 0;
    }

    // -------------------------------------
    // Generated accessors
    // -------------------------------------
    @NonNull
    public String getId() {
        return id;
    }

    @NonNull
    public String getUserId() {
        return userId;
    }

    @NonNull
    public VitalType getType() {
        return type;
    }

    @Nullable
    public Double getNumericValue() {
        return numericValue;
    }

    @Nullable
    public String getStringValue() {
        return stringValue;
    }

    @Nullable
    public String getUnit() {
        return unit;
    }

    public long getRecordedAt() {
        return recordedAt;
    }

    public boolean isSynced() {
        return synced;
    }

    @Nullable
    public String getNote() {
        return note;
    }

    // -------------------------------------
    // equals / hashCode / toString
    // -------------------------------------
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof VitalsRecord)) return false;
        VitalsRecord that = (VitalsRecord) o;
        return recordedAt == that.recordedAt &&
                synced == that.synced &&
                id.equals(that.id) &&
                userId.equals(that.userId) &&
                type == that.type &&
                Objects.equals(numericValue, that.numericValue) &&
                Objects.equals(stringValue, that.stringValue) &&
                Objects.equals(unit, that.unit) &&
                Objects.equals(note, that.note);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, userId, type, numericValue, stringValue, unit, recordedAt, synced, note);
    }

    @Override
    public String toString() {
        return "VitalsRecord{" +
                "id='" + id + '\'' +
                ", userId='" + userId + '\'' +
                ", type=" + type +
                ", numericValue=" + numericValue +
                ", stringValue='" + stringValue + '\'' +
                ", unit='" + unit + '\'' +
                ", recordedAt=" + recordedAt +
                ", synced=" + synced +
                ", note='" + note + '\'' +
                '}';
    }

    // -------------------------------------
    // Room TypeConverters
    // -------------------------------------
    public enum VitalType {
        HEART_RATE,
        BLOOD_PRESSURE,
        BLOOD_GLUCOSE,
        WEIGHT,
        TEMPERATURE,
        OXYGEN_SATURATION,
        RESPIRATORY_RATE,
        CUSTOM
    }

    public static class VitalTypeConverter {

        @TypeConverter
        public static String toString(@Nullable VitalType type) {
            return type == null ? null : type.name();
        }

        @TypeConverter
        public static VitalType fromString(@Nullable String str) {
            return str == null ? null : VitalType.valueOf(str);
        }
    }
}