/*
 * WellSphere Connect
 *
 * Copyright (c) 2024 WellSphere
 *
 * Licensed under the Apache License, Version 2.0 (the "License")
 */

package com.wellsphere.connect.data.model;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.annotation.VisibleForTesting;
import androidx.room.ColumnInfo;
import androidx.room.Entity;
import androidx.room.Ignore;
import androidx.room.PrimaryKey;
import androidx.room.TypeConverter;
import androidx.room.TypeConverters;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;
import com.google.gson.reflect.TypeToken;

import java.io.Serializable;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Objects;

/**
 * Immutable data-model representing a clinician's public-facing profile.
 * <p>
 * This entity is:
 * <ul>
 *     <li>Room-compatible (local persistence)</li>
 *     <li>Parcelable (inter-component transfer)</li>
 *     <li>Serializable to/from JSON via Gson</li>
 * </ul>
 *
 * Right-to-modify is restricted to the {@link Builder} allowing us
 * to maintain referential transparency throughout the app-layer.
 */
@Entity(tableName = "clinician_profile")
@TypeConverters(ClinicianProfile.LanguageListConverter.class)
public final class ClinicianProfile implements Parcelable, Serializable {

    //region Room Columns

    @PrimaryKey
    @NonNull
    @ColumnInfo(name = "clinician_id")
    @SerializedName("clinician_id")
    private final String clinicianId;

    @NonNull
    @ColumnInfo(name = "first_name")
    @SerializedName("first_name")
    private final String firstName;

    @NonNull
    @ColumnInfo(name = "last_name")
    @SerializedName("last_name")
    private final String lastName;

    @Nullable
    @ColumnInfo(name = "credentials")
    private final String credentials;               // "MD", "RN", etc.

    @Nullable
    @ColumnInfo(name = "specialization")
    private final String specialization;            // "Cardiology", etc.

    @Nullable
    @ColumnInfo(name = "phone")
    private final String phone;

    @Nullable
    @ColumnInfo(name = "email")
    private final String email;

    @Nullable
    @ColumnInfo(name = "avatar_url")
    @SerializedName("avatar_url")
    private final String avatarUrl;

    @Nullable
    @ColumnInfo(name = "hospital_affiliation")
    @SerializedName("hospital_affiliation")
    private final String hospitalAffiliation;

    @Nullable
    @ColumnInfo(name = "license_number")
    @SerializedName("license_number")
    private final String licenseNumber;

    @ColumnInfo(name = "rating")
    private final float rating;                     // 0f – 5f

    @Nullable
    @ColumnInfo(name = "languages")
    private final List<String> languages;           // i18n list

    @Nullable
    @ColumnInfo(name = "timezone")
    private final String timezone;

    //endregion

    //region Constructor

    private ClinicianProfile(Builder builder) {
        this.clinicianId         = builder.clinicianId;
        this.firstName           = builder.firstName;
        this.lastName            = builder.lastName;
        this.credentials         = builder.credentials;
        this.specialization      = builder.specialization;
        this.phone               = builder.phone;
        this.email               = builder.email;
        this.avatarUrl           = builder.avatarUrl;
        this.hospitalAffiliation = builder.hospitalAffiliation;
        this.licenseNumber       = builder.licenseNumber;
        this.rating              = builder.rating;
        this.languages           = Collections.unmodifiableList(builder.languages); // defensive copy
        this.timezone            = builder.timezone;
    }

    //endregion

    //region Builder

    /**
     * Fluent builder with validation logic.
     */
    public static final class Builder {
        private static final float MIN_RATING = 0f;
        private static final float MAX_RATING = 5f;

        private String clinicianId;
        private String firstName;
        private String lastName;
        private String credentials;
        private String specialization;
        private String phone;
        private String email;
        private String avatarUrl;
        private String hospitalAffiliation;
        private String licenseNumber;
        private float rating;
        private List<String> languages = new ArrayList<>();
        private String timezone;

        public Builder(@NonNull String clinicianId,
                       @NonNull String firstName,
                       @NonNull String lastName) {
            this.clinicianId = Objects.requireNonNull(clinicianId, "clinicianId == null").trim();
            this.firstName   = Objects.requireNonNull(firstName,   "firstName == null").trim();
            this.lastName    = Objects.requireNonNull(lastName,    "lastName == null").trim();
        }

        public Builder credentials(@Nullable String credentials) {
            this.credentials = sanitize(credentials);
            return this;
        }

        public Builder specialization(@Nullable String specialization) {
            this.specialization = sanitize(specialization);
            return this;
        }

        public Builder phone(@Nullable String phone) {
            this.phone = sanitize(phone);
            return this;
        }

        public Builder email(@Nullable String email) {
            this.email = sanitize(email);
            return this;
        }

        public Builder avatarUrl(@Nullable String avatarUrl) {
            this.avatarUrl = sanitize(avatarUrl);
            return this;
        }

        public Builder hospitalAffiliation(@Nullable String hospitalAffiliation) {
            this.hospitalAffiliation = sanitize(hospitalAffiliation);
            return this;
        }

        public Builder licenseNumber(@Nullable String licenseNumber) {
            this.licenseNumber = sanitize(licenseNumber);
            return this;
        }

        public Builder rating(float rating) {
            this.rating = rating;
            return this;
        }

        public Builder languages(@Nullable List<String> languages) {
            this.languages = languages != null ? new ArrayList<>(languages) : new ArrayList<>();
            return this;
        }

        public Builder timezone(@Nullable String timezone) {
            this.timezone = sanitize(timezone);
            return this;
        }

        /** Build after validation. */
        public ClinicianProfile build() {
            validate();
            return new ClinicianProfile(this);
        }

        private void validate() {
            if (rating < MIN_RATING || rating > MAX_RATING) {
                throw new IllegalArgumentException(
                        String.format(Locale.US, "rating %.2f must be between %.1f and %.1f",
                                rating, MIN_RATING, MAX_RATING));
            }
        }

        @Nullable
        private static String sanitize(@Nullable String input) {
            return input == null ? null : input.trim();
        }
    }

    //endregion

    //region Parcelable

    protected ClinicianProfile(Parcel in) {
        clinicianId         = Objects.requireNonNull(in.readString());
        firstName           = Objects.requireNonNull(in.readString());
        lastName            = Objects.requireNonNull(in.readString());
        credentials         = in.readString();
        specialization      = in.readString();
        phone               = in.readString();
        email               = in.readString();
        avatarUrl           = in.readString();
        hospitalAffiliation = in.readString();
        licenseNumber       = in.readString();
        rating              = in.readFloat();
        languages           = new ArrayList<>();
        in.readStringList(languages);
        timezone            = in.readString();
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeString(clinicianId);
        dest.writeString(firstName);
        dest.writeString(lastName);
        dest.writeString(credentials);
        dest.writeString(specialization);
        dest.writeString(phone);
        dest.writeString(email);
        dest.writeString(avatarUrl);
        dest.writeString(hospitalAffiliation);
        dest.writeString(licenseNumber);
        dest.writeFloat(rating);
        dest.writeStringList(languages);
        dest.writeString(timezone);
    }

    @Override
    public int describeContents() {
        return 0;
    }

    public static final Parcelable.Creator<ClinicianProfile> CREATOR =
            new Parcelable.Creator<ClinicianProfile>() {
                @Override
                public ClinicianProfile createFromParcel(Parcel in) {
                    return new ClinicianProfile(in);
                }

                @Override
                public ClinicianProfile[] newArray(int size) {
                    return new ClinicianProfile[size];
                }
            };

    //endregion

    //region Accessors

    @NonNull public String getClinicianId()         { return clinicianId; }
    @NonNull public String getFirstName()           { return firstName; }
    @NonNull public String getLastName()            { return lastName; }
    @Nullable public String getCredentials()        { return credentials; }
    @Nullable public String getSpecialization()     { return specialization; }
    @Nullable public String getPhone()              { return phone; }
    @Nullable public String getEmail()              { return email; }
    @Nullable public String getAvatarUrl()          { return avatarUrl; }
    @Nullable public String getHospitalAffiliation(){ return hospitalAffiliation; }
    @Nullable public String getLicenseNumber()      { return licenseNumber; }
    public float  getRating()                       { return rating; }
    @NonNull public List<String> getLanguages()     { return languages; }
    @Nullable public String getTimezone()           { return timezone; }

    /**
     * Convenience method for full-name rendering.
     */
    @NonNull
    public String getDisplayName() {
        return String.format(Locale.getDefault(), "%s %s", firstName, lastName);
    }

    //endregion

    //region Mutations

    /**
     * Returns a new instance with avatarUrl updated.
     */
    public ClinicianProfile withAvatar(@Nullable String newAvatarUrl) {
        return new Builder(clinicianId, firstName, lastName)
                .credentials(credentials)
                .specialization(specialization)
                .phone(phone)
                .email(email)
                .avatarUrl(newAvatarUrl)
                .hospitalAffiliation(hospitalAffiliation)
                .licenseNumber(licenseNumber)
                .rating(rating)
                .languages(languages)
                .timezone(timezone)
                .build();
    }

    //endregion

    //region JSON Serialization helpers

    @Ignore
    private static final Gson GSON = new Gson();

    public String toJson() {
        return GSON.toJson(this);
    }

    public static ClinicianProfile fromJson(@NonNull String json) {
        return GSON.fromJson(json, ClinicianProfile.class);
    }

    //endregion

    //region Overrides

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof ClinicianProfile)) return false;
        ClinicianProfile that = (ClinicianProfile) o;
        return clinicianId.equals(that.clinicianId)
                && firstName.equals(that.firstName)
                && lastName.equals(that.lastName)
                && Objects.equals(credentials, that.credentials)
                && Objects.equals(specialization, that.specialization)
                && Objects.equals(phone, that.phone)
                && Objects.equals(email, that.email)
                && Objects.equals(avatarUrl, that.avatarUrl)
                && Objects.equals(hospitalAffiliation, that.hospitalAffiliation)
                && Objects.equals(licenseNumber, that.licenseNumber)
                && Float.compare(that.rating, rating) == 0
                && Objects.equals(languages, that.languages)
                && Objects.equals(timezone, that.timezone);
    }

    @Override
    public int hashCode() {
        return Objects.hash(clinicianId, firstName, lastName, credentials,
                specialization, phone, email, avatarUrl, hospitalAffiliation,
                licenseNumber, rating, languages, timezone);
    }

    @Override
    public String toString() {
        return "ClinicianProfile{" +
                "clinicianId='" + clinicianId + '\'' +
                ", name='" + getDisplayName() + '\'' +
                ", credentials='" + credentials + '\'' +
                ", specialization='" + specialization + '\'' +
                ", rating=" + rating +
                '}';
    }

    //endregion

    //region Room TypeConverter for List<String>

    /**
     * Room converter: List&lt;String&gt; ↔ JSON.
     * Kept inside model to avoid polluting the db module.
     */
    public static final class LanguageListConverter {
        private static final Gson gson = new Gson();
        private static final Type  type = new TypeToken<List<String>>(){}.getType();

        @TypeConverter
        public static List<String> fromJson(@Nullable String json) {
            return json == null
                    ? new ArrayList<>()
                    : gson.fromJson(json, type);
        }

        @TypeConverter
        public static String toJson(@Nullable List<String> list) {
            return list == null || list.isEmpty()
                    ? null
                    : gson.toJson(list, type);
        }
    }

    //endregion

    //region Testing Helpers

    /**
     * Generates a dummy instance for UI previews / screenshot tests.
     */
    @VisibleForTesting
    public static ClinicianProfile stub() {
        return new Builder("c-001", "Ada", "Lovelace")
                .credentials("MD")
                .specialization("Neurology")
                .avatarUrl("https://cdn.wellsphere.com/avatars/ada.png")
                .email("ada.lovelace@wellsphere.com")
                .phone("+1-555-0101")
                .hospitalAffiliation("WellSphere General Hospital")
                .licenseNumber("MD-123456")
                .rating(4.9f)
                .languages(List.of("en", "fr"))
                .timezone("America/Los_Angeles")
                .build();
    }

    //endregion
}