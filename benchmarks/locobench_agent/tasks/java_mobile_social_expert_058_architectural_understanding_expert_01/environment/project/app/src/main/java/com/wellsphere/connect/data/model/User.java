package com.wellsphere.connect.data.model;

import android.os.Parcel;
import android.os.Parcelable;
import android.text.TextUtils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.ColumnInfo;
import androidx.room.Entity;
import androidx.room.PrimaryKey;
import androidx.room.TypeConverter;
import androidx.room.TypeConverters;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;
import com.google.gson.reflect.TypeToken;

import java.lang.reflect.Type;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Immutable data class that represents a user inside the WellSphere Connect ecosystem.
 *
 * <p>The class is designed to function across multiple application layers:
 *  • Local storage      – Room annotations (@Entity, @ColumnInfo, @TypeConverters). <br>
 *  • Remote JSON APIs   – Gson annotations (@SerializedName). <br>
 *  • IPC / Bundles      – Parcelable implementation. <br>
 *
 * It purposefully avoids framework-specific logic beyond the annotations required for the above
 * concerns, keeping the model deterministic and side-effect free.
 */
@Entity(tableName = "users")
@TypeConverters({User.RoleListConverter.class})
public final class User implements Parcelable {

    /* ----------------------------- Static Helpers ----------------------------- */

    private static final Gson GSON = new Gson();

    /* --------------------------------- Fields -------------------------------- */

    @PrimaryKey
    @NonNull
    @SerializedName("uuid")
    @ColumnInfo(name = "uuid")
    private final String uuid;

    @SerializedName("full_name")
    @ColumnInfo(name = "full_name")
    private final String fullName;

    @SerializedName("email")
    @ColumnInfo(name = "email")
    private final String email;

    @SerializedName("phone_number")
    @ColumnInfo(name = "phone_number")
    private final String phoneNumber;

    @SerializedName("avatar_url")
    @ColumnInfo(name = "avatar_url")
    private final String avatarUrl;

    @SerializedName("dob_epoch")
    @ColumnInfo(name = "dob_epoch")
    private final long dateOfBirthEpochSec;

    @SerializedName("gender")
    @ColumnInfo(name = "gender")
    private final Gender gender;

    @SerializedName("roles")
    @ColumnInfo(name = "roles")
    private final List<Role> roles;

    @SerializedName("bio")
    @ColumnInfo(name = "bio")
    private final String biography;

    @SerializedName("location")
    @ColumnInfo(name = "location")
    private final String location;

    @SerializedName("biometric_enabled")
    @ColumnInfo(name = "biometric_enabled")
    private final boolean biometricEnabled;

    @SerializedName("created_at")
    @ColumnInfo(name = "created_at")
    private final long createdAtEpochSec;

    @SerializedName("updated_at")
    @ColumnInfo(name = "updated_at")
    private final long updatedAtEpochSec;

    /* -------------------------------- Builder -------------------------------- */

    /**
     * Builder used to instantiate immutable {@link User} objects with compile-time safety.
     *
     * Validation is performed in {@link #build()} to ensure that required fields are present
     * before an object is created.
     */
    public static final class Builder {

        private String uuid;
        private String fullName;
        private String email;
        private String phoneNumber;
        private String avatarUrl;
        private long dateOfBirthEpochSec;
        private Gender gender = Gender.UNKNOWN;
        private List<Role> roles = Collections.singletonList(Role.PATIENT);
        private String biography;
        private String location;
        private boolean biometricEnabled;
        private long createdAtEpochSec;
        private long updatedAtEpochSec;

        public Builder() {
            // Defaults
            long now = System.currentTimeMillis() / 1000;
            createdAtEpochSec = now;
            updatedAtEpochSec = now;
        }

        public Builder(@NonNull User source) {
            Objects.requireNonNull(source);
            uuid = source.uuid;
            fullName = source.fullName;
            email = source.email;
            phoneNumber = source.phoneNumber;
            avatarUrl = source.avatarUrl;
            dateOfBirthEpochSec = source.dateOfBirthEpochSec;
            gender = source.gender;
            roles = source.roles;
            biography = source.biography;
            location = source.location;
            biometricEnabled = source.biometricEnabled;
            createdAtEpochSec = source.createdAtEpochSec;
            updatedAtEpochSec = source.updatedAtEpochSec;
        }

        public Builder uuid(@NonNull String uuid) {
            this.uuid = uuid;
            return this;
        }

        public Builder fullName(@Nullable String fullName) {
            this.fullName = fullName;
            return this;
        }

        public Builder email(@Nullable String email) {
            this.email = email;
            return this;
        }

        public Builder phoneNumber(@Nullable String phoneNumber) {
            this.phoneNumber = phoneNumber;
            return this;
        }

        public Builder avatarUrl(@Nullable String avatarUrl) {
            this.avatarUrl = avatarUrl;
            return this;
        }

        public Builder dateOfBirthEpochSec(long epochSec) {
            this.dateOfBirthEpochSec = epochSec;
            return this;
        }

        public Builder gender(@NonNull Gender gender) {
            this.gender = gender;
            return this;
        }

        public Builder roles(@NonNull List<Role> roles) {
            this.roles = roles;
            return this;
        }

        public Builder biography(@Nullable String biography) {
            this.biography = biography;
            return this;
        }

        public Builder location(@Nullable String location) {
            this.location = location;
            return this;
        }

        public Builder biometricEnabled(boolean biometricEnabled) {
            this.biometricEnabled = biometricEnabled;
            return this;
        }

        public Builder createdAtEpochSec(long epochSec) {
            this.createdAtEpochSec = epochSec;
            return this;
        }

        public Builder updatedAtEpochSec(long epochSec) {
            this.updatedAtEpochSec = epochSec;
            return this;
        }

        /**
         * Validates required fields and returns an immutable {@link User} instance.
         *
         * @throws IllegalStateException if mandatory fields are missing.
         */
        public User build() {
            if (TextUtils.isEmpty(uuid)) {
                throw new IllegalStateException("UUID is mandatory and cannot be null or empty");
            }
            if (roles == null || roles.isEmpty()) {
                throw new IllegalStateException("User must contain at least one role");
            }
            return new User(this);
        }
    }

    /* ------------------------------ Constructor ------------------------------ */

    private User(Builder builder) {
        uuid = builder.uuid;
        fullName = builder.fullName;
        email = builder.email;
        phoneNumber = builder.phoneNumber;
        avatarUrl = builder.avatarUrl;
        dateOfBirthEpochSec = builder.dateOfBirthEpochSec;
        gender = builder.gender;
        roles = Collections.unmodifiableList(builder.roles);
        biography = builder.biography;
        location = builder.location;
        biometricEnabled = builder.biometricEnabled;
        createdAtEpochSec = builder.createdAtEpochSec;
        updatedAtEpochSec = builder.updatedAtEpochSec;
    }

    /* ------------------------------- Getters --------------------------------- */

    @NonNull public String getUuid()                { return uuid; }
    @Nullable public String getFullName()           { return fullName; }
    @Nullable public String getEmail()              { return email; }
    @Nullable public String getPhoneNumber()        { return phoneNumber; }
    @Nullable public String getAvatarUrl()          { return avatarUrl; }
    public long getDateOfBirthEpochSec()            { return dateOfBirthEpochSec; }
    @NonNull public Gender getGender()              { return gender; }
    @NonNull public List<Role> getRoles()           { return roles; }
    @Nullable public String getBiography()          { return biography; }
    @Nullable public String getLocation()           { return location; }
    public boolean isBiometricEnabled()             { return biometricEnabled; }
    public long getCreatedAtEpochSec()              { return createdAtEpochSec; }
    public long getUpdatedAtEpochSec()              { return updatedAtEpochSec; }

    /* ------------------------- Domain Convenience ---------------------------- */

    /**
     * Indicates whether the user has elevated privileges (i.e., is a clinician or admin).
     */
    public boolean hasElevatedPrivileges() {
        return roles.contains(Role.CLINICIAN) || roles.contains(Role.ADMIN);
    }

    /**
     * Creates a new {@link Builder} initialized with a copy of the current user.
     */
    public Builder toBuilder() {
        return new Builder(this);
    }

    /* ---------------------------- Parcelable --------------------------------- */

    protected User(Parcel in) {
        uuid = Objects.requireNonNull(in.readString());
        fullName = in.readString();
        email = in.readString();
        phoneNumber = in.readString();
        avatarUrl = in.readString();
        dateOfBirthEpochSec = in.readLong();
        gender = Gender.valueOf(in.readString());
        roles = GSON.fromJson(in.readString(), new TypeToken<List<Role>>() {}.getType());
        biography = in.readString();
        location = in.readString();
        biometricEnabled = in.readByte() != 0;
        createdAtEpochSec = in.readLong();
        updatedAtEpochSec = in.readLong();
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeString(uuid);
        dest.writeString(fullName);
        dest.writeString(email);
        dest.writeString(phoneNumber);
        dest.writeString(avatarUrl);
        dest.writeLong(dateOfBirthEpochSec);
        dest.writeString(gender.name());
        dest.writeString(GSON.toJson(roles));
        dest.writeString(biography);
        dest.writeString(location);
        dest.writeByte((byte) (biometricEnabled ? 1 : 0));
        dest.writeLong(createdAtEpochSec);
        dest.writeLong(updatedAtEpochSec);
    }

    @Override
    public int describeContents() {
        return 0;
    }

    public static final Creator<User> CREATOR = new Creator<User>() {
        @Override public User createFromParcel(Parcel in) { return new User(in); }
        @Override public User[] newArray(int size)        { return new User[size]; }
    };

    /* ---------------------------- Converters --------------------------------- */

    /**
     * Room converter that serializes/deserializes the list of user roles.
     * The conversion uses a compact JSON representation to remain forward-compatible
     * with additional future roles.
     */
    public static final class RoleListConverter {

        private static final Type LIST_TYPE = new TypeToken<List<Role>>() {}.getType();

        @TypeConverter
        public static String fromRoles(@Nullable List<Role> roles) {
            return roles == null ? "[]" : GSON.toJson(roles, LIST_TYPE);
        }

        @TypeConverter
        public static List<Role> toRoles(@Nullable String value) {
            if (TextUtils.isEmpty(value)) {
                return Collections.emptyList();
            }
            try {
                return GSON.fromJson(value, LIST_TYPE);
            } catch (Exception ex) {
                // Gracefully degrade by returning an empty list to keep the app from crashing.
                return Collections.emptyList();
            }
        }
    }

    /* --------------------------------- Enums -------------------------------- */

    /**
     * Clinically-aligned gender representation used by the application.
     */
    public enum Gender {
        MALE,
        FEMALE,
        OTHER,
        UNKNOWN
    }

    /**
     * Enumerates the high-level roles a user can assume within the platform.
     * Multiple roles may be assigned to the same user.
     */
    public enum Role {
        PATIENT,
        CAREGIVER,
        CLINICIAN,
        ADMIN
    }

    /* ---------------------------- Object utils ------------------------------ */

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof User)) return false;

        User other = (User) o;
        return uuid.equals(other.uuid) &&
                biometricEnabled == other.biometricEnabled &&
                dateOfBirthEpochSec == other.dateOfBirthEpochSec &&
                createdAtEpochSec == other.createdAtEpochSec &&
                updatedAtEpochSec == other.updatedAtEpochSec &&
                Objects.equals(fullName, other.fullName) &&
                Objects.equals(email, other.email) &&
                Objects.equals(phoneNumber, other.phoneNumber) &&
                Objects.equals(avatarUrl, other.avatarUrl) &&
                gender == other.gender &&
                Objects.equals(roles, other.roles) &&
                Objects.equals(biography, other.biography) &&
                Objects.equals(location, other.location);
    }

    @Override
    public int hashCode() {
        return Objects.hash(uuid);
    }

    @Override
    public String toString() {
        return "User{" +
                "uuid='" + uuid + '\'' +
                ", fullName='" + fullName + '\'' +
                ", roles=" + roles +
                '}';
    }
}