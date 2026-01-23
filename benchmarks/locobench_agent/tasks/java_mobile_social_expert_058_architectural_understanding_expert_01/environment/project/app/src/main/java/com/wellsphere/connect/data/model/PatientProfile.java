```java
package com.wellsphere.connect.data.model;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.Entity;
import androidx.room.PrimaryKey;
import androidx.room.TypeConverter;
import androidx.room.TypeConverters;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;
import com.google.gson.reflect.TypeToken;

import java.lang.reflect.Type;
import java.util.Calendar;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Objects;

/**
 * Immutable domain/entity model that represents a unique patient profile within
 * the WellSphere Connect ecosystem.
 *
 * The class fulfills the following responsibilities:
 *  • Room database entity (offline cache)
 *  • Gson-serialisable DTO for network exchange
 *  • Parcelable for efficient IPC / Intent transfer
 *  • Provides basic domain logic (age calculation, anonymisation, validation)
 *
 * NOTE: In a heavily regulated environment such as healthcare, it is critical
 *       to avoid leaking personally-identifiable information (PII) by accident.
 *       The {@link #anonymised()} helper returns a reduced view that can safely
 *       be shared to social feeds or analytics pipelines.
 */
@Entity(tableName = "patient_profiles")
@TypeConverters(PatientProfile.Converters.class)
public final class PatientProfile implements Parcelable {

    // ------------------------------------ //
    // Gson / Room mapped fields            //
    // ------------------------------------ //

    @PrimaryKey
    @NonNull
    @SerializedName("id")
    private final String id;

    @NonNull
    @SerializedName("first_name")
    private final String firstName;

    @NonNull
    @SerializedName("last_name")
    private final String lastName;

    @NonNull
    @SerializedName("dob")
    private final Date dateOfBirth;

    @NonNull
    @SerializedName("gender")
    private final Gender gender;

    @Nullable
    @SerializedName("email")
    private final String email;

    @Nullable
    @SerializedName("phone")
    private final String phoneNumber;

    @Nullable
    @SerializedName("photo_url")
    private final String profilePhotoUrl;

    @NonNull
    @SerializedName("allergies")
    private final List<String> allergies;

    @NonNull
    @SerializedName("conditions")
    private final List<String> medicalConditions;

    @NonNull
    @SerializedName("last_updated")
    private final Date lastUpdated;

    @SerializedName("active_care_plan")
    private final boolean activeCarePlan;

    // ------------------------------------ //
    // Constructors                         //
    // ------------------------------------ //

    private PatientProfile(Builder builder) {
        this.id = builder.id;
        this.firstName = builder.firstName;
        this.lastName = builder.lastName;
        this.dateOfBirth = builder.dateOfBirth;
        this.gender = builder.gender;
        this.email = builder.email;
        this.phoneNumber = builder.phoneNumber;
        this.profilePhotoUrl = builder.profilePhotoUrl;
        this.allergies = Collections.unmodifiableList(builder.allergies);
        this.medicalConditions = Collections.unmodifiableList(builder.medicalConditions);
        this.lastUpdated = builder.lastUpdated != null ? builder.lastUpdated : new Date();
        this.activeCarePlan = builder.activeCarePlan;
    }

    // ------------------------------------ //
    // Parcelable implementation            //
    // ------------------------------------ //

    protected PatientProfile(Parcel in) {
        id = Objects.requireNonNull(in.readString());
        firstName = Objects.requireNonNull(in.readString());
        lastName = Objects.requireNonNull(in.readString());
        dateOfBirth = new Date(in.readLong());
        gender = Gender.valueOf(Objects.requireNonNull(in.readString()));
        email = in.readString();
        phoneNumber = in.readString();
        profilePhotoUrl = in.readString();
        allergies = Converters.fromJson(in.readString());
        medicalConditions = Converters.fromJson(in.readString());
        lastUpdated = new Date(in.readLong());
        activeCarePlan = in.readByte() != 0;
    }

    public static final Creator<PatientProfile> CREATOR = new Creator<PatientProfile>() {
        @Override
        public PatientProfile createFromParcel(Parcel in) {
            return new PatientProfile(in);
        }

        @Override
        public PatientProfile[] newArray(int size) {
            return new PatientProfile[size];
        }
    };

    @Override
    public int describeContents() {
        return 0; // No File descriptors
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeString(id);
        dest.writeString(firstName);
        dest.writeString(lastName);
        dest.writeLong(dateOfBirth.getTime());
        dest.writeString(gender.name());
        dest.writeString(email);
        dest.writeString(phoneNumber);
        dest.writeString(profilePhotoUrl);
        dest.writeString(Converters.toJson(allergies));
        dest.writeString(Converters.toJson(medicalConditions));
        dest.writeLong(lastUpdated.getTime());
        dest.writeByte((byte) (activeCarePlan ? 1 : 0));
    }

    // ------------------------------------ //
    // Business / domain logic              //
    // ------------------------------------ //

    /**
     * Returns the patient’s age in whole calendar years.
     */
    public int getAge() {
        Calendar dob = Calendar.getInstance();
        dob.setTime(dateOfBirth);
        Calendar today = Calendar.getInstance();

        int age = today.get(Calendar.YEAR) - dob.get(Calendar.YEAR);

        // If today's date is before the patient's birthday, subtract a year.
        if (today.get(Calendar.DAY_OF_YEAR) < dob.get(Calendar.DAY_OF_YEAR)) {
            age--;
        }
        return age;
    }

    /**
     * Convenience flag.
     */
    public boolean isMinor() {
        return getAge() < 18;
    }

    /**
     * Returns a view that strips PII and can be forwarded to social feeds.
     */
    public AnonymisedPatient anonymised() {
        return new AnonymisedPatient(id, getAge(), gender, medicalConditions, activeCarePlan);
    }

    // ------------------------------------ //
    // Accessors                            //
    // ------------------------------------ //

    @NonNull public String getId() { return id; }

    @NonNull public String getFirstName() { return firstName; }

    @NonNull public String getLastName() { return lastName; }

    @NonNull public Date getDateOfBirth() { return new Date(dateOfBirth.getTime()); }

    @NonNull public Gender getGender() { return gender; }

    @Nullable public String getEmail() { return email; }

    @Nullable public String getPhoneNumber() { return phoneNumber; }

    @Nullable public String getProfilePhotoUrl() { return profilePhotoUrl; }

    @NonNull public List<String> getAllergies() { return allergies; }

    @NonNull public List<String> getMedicalConditions() { return medicalConditions; }

    @NonNull public Date getLastUpdated() { return new Date(lastUpdated.getTime()); }

    public boolean hasActiveCarePlan() { return activeCarePlan; }

    // ------------------------------------ //
    // Object overrides                     //
    // ------------------------------------ //

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof PatientProfile)) return false;
        PatientProfile that = (PatientProfile) o;
        return activeCarePlan == that.activeCarePlan &&
                id.equals(that.id) &&
                firstName.equals(that.firstName) &&
                lastName.equals(that.lastName) &&
                dateOfBirth.equals(that.dateOfBirth) &&
                gender == that.gender &&
                Objects.equals(email, that.email) &&
                Objects.equals(phoneNumber, that.phoneNumber) &&
                Objects.equals(profilePhotoUrl, that.profilePhotoUrl) &&
                allergies.equals(that.allergies) &&
                medicalConditions.equals(that.medicalConditions) &&
                lastUpdated.equals(that.lastUpdated);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, firstName, lastName, dateOfBirth, gender, email,
                phoneNumber, profilePhotoUrl, allergies, medicalConditions, lastUpdated,
                activeCarePlan);
    }

    @Override
    public String toString() {
        return "PatientProfile{" +
                "id='" + id + '\'' +
                ", name='" + firstName + ' ' + lastName + '\'' +
                ", gender=" + gender +
                ", age=" + getAge() +
                ", conditions=" + medicalConditions +
                ", activeCarePlan=" + activeCarePlan +
                '}';
    }

    // ------------------------------------ //
    // Builder                              //
    // ------------------------------------ //

    public static class Builder {
        private final String id;
        private final String firstName;
        private final String lastName;
        private final Date dateOfBirth;
        private final Gender gender;

        private String email;
        private String phoneNumber;
        private String profilePhotoUrl;
        private List<String> allergies = Collections.emptyList();
        private List<String> medicalConditions = Collections.emptyList();
        private Date lastUpdated;
        private boolean activeCarePlan;

        /**
         * Builder with required fields.
         *
         * @param id            Unique (UUID) identifier.
         * @param firstName     Patient first name.
         * @param lastName      Patient last name.
         * @param dateOfBirth   Patient date of birth.
         * @param gender        Patient gender.
         */
        public Builder(@NonNull String id,
                       @NonNull String firstName,
                       @NonNull String lastName,
                       @NonNull Date dateOfBirth,
                       @NonNull Gender gender) {

            if (id.isEmpty()) throw new IllegalArgumentException("id must not be empty");
            if (firstName.isEmpty()) throw new IllegalArgumentException("firstName must not be empty");
            if (lastName.isEmpty()) throw new IllegalArgumentException("lastName must not be empty");

            this.id = id;
            this.firstName = firstName;
            this.lastName = lastName;
            this.dateOfBirth = new Date(dateOfBirth.getTime()); // defensive copy
            this.gender = gender;
        }

        public Builder email(@Nullable String email) {
            this.email = email;
            return this;
        }

        public Builder phoneNumber(@Nullable String phoneNumber) {
            this.phoneNumber = phoneNumber;
            return this;
        }

        public Builder profilePhotoUrl(@Nullable String url) {
            this.profilePhotoUrl = url;
            return this;
        }

        public Builder allergies(@NonNull List<String> allergies) {
            this.allergies = Collections.unmodifiableList(allergies);
            return this;
        }

        public Builder medicalConditions(@NonNull List<String> conditions) {
            this.medicalConditions = Collections.unmodifiableList(conditions);
            return this;
        }

        public Builder lastUpdated(@NonNull Date lastUpdated) {
            this.lastUpdated = new Date(lastUpdated.getTime());
            return this;
        }

        public Builder activeCarePlan(boolean activeCarePlan) {
            this.activeCarePlan = activeCarePlan;
            return this;
        }

        public PatientProfile build() {
            return new PatientProfile(this);
        }
    }

    // ------------------------------------ //
    // Anonymised sub-view                  //
    // ------------------------------------ //

    /**
     * Lightweight representation without PII. Safe for public sharing.
     */
    public static final class AnonymisedPatient {
        public final String id;
        public final int age;
        public final Gender gender;
        public final List<String> conditions;
        public final boolean activeCarePlan;

        AnonymisedPatient(String id, int age, Gender gender, List<String> conditions, boolean activeCarePlan) {
            this.id = id;
            this.age = age;
            this.gender = gender;
            this.conditions = Collections.unmodifiableList(conditions);
            this.activeCarePlan = activeCarePlan;
        }

        @Override
        public String toString() {
            return "AnonymisedPatient{" +
                    "id='" + id + '\'' +
                    ", age=" + age +
                    ", gender=" + gender +
                    ", conditions=" + conditions +
                    ", activeCarePlan=" + activeCarePlan +
                    '}';
        }
    }

    // ------------------------------------ //
    // Enum                                //
    // ------------------------------------ //

    public enum Gender { MALE, FEMALE, OTHER, UNDISCLOSED }

    // ------------------------------------ //
    // Room-friendly type converters        //
    // ------------------------------------ //

    public static class Converters {
        private static final Gson gson = new Gson();
        private static final Type LIST_STRING = new TypeToken<List<String>>() {}.getType();

        @TypeConverter
        public static String toJson(List<String> list) {
            return gson.toJson(list);
        }

        @TypeConverter
        public static List<String> fromJson(String json) {
            if (json == null || json.isEmpty()) return Collections.emptyList();
            return gson.fromJson(json, LIST_STRING);
        }

        @TypeConverter
        public static Long fromDate(Date date) {
            return date != null ? date.getTime() : null;
        }

        @TypeConverter
        public static Date toDate(Long timestamp) {
            return timestamp != null ? new Date(timestamp) : null;
        }
    }
}
```