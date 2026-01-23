package com.wellsphere.connect.data.model;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.ColumnInfo;
import androidx.room.Entity;
import androidx.room.Ignore;
import androidx.room.PrimaryKey;
import androidx.room.TypeConverters;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;
import com.wellsphere.connect.data.persistence.converter.LocalDateConverter;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Immutable domain model representing a plan of care that may contain several
 * {@link CareTask}s.  The entity is persisted locally via Room, serialized from /
 * to JSON via Moshi, and transferred across Android components via {@link Parcelable}.
 *
 * A {@code CarePlan} can be marked as premium; consumers should verify purchase
 * state (via BillingClient) before unlocking premium content in the UI layer.
 */
@JsonClass(generateAdapter = true)
@Entity(tableName = "care_plans")
@TypeConverters(LocalDateConverter.class)
public final class CarePlan implements Parcelable {

    /* ***********************************************************************
     *  Constants
     * ***********************************************************************/
    public static final String STATUS_ACTIVE  = "ACTIVE";
    public static final String STATUS_PAUSED  = "PAUSED";
    public static final String STATUS_ARCHIVED = "ARCHIVED";

    /* ***********************************************************************
     *  Fields
     * ***********************************************************************/
    @PrimaryKey
    @NonNull
    @Json(name = "id")
    private final String id;

    @NonNull
    @Json(name = "title")
    private final String title;

    @Nullable
    @Json(name = "description")
    private final String description;

    @Nullable
    @ColumnInfo(name = "start_date")
    @Json(name = "start_date")
    private final LocalDate startDate;

    @Nullable
    @ColumnInfo(name = "end_date")
    @Json(name = "end_date")
    private final LocalDate endDate;

    @Json(name = "status")
    private final String status; // Should map to one of the STATUS_* constants

    @Json(name = "is_premium")
    @ColumnInfo(name = "is_premium")
    private final boolean isPremium;

    @NonNull
    @Json(name = "tasks")
    @Ignore // Tasks are kept in a dedicated Room table – ignored here to avoid duplication
    private final List<CareTask> tasks;

    /* ***********************************************************************
     *  Constructors
     * ***********************************************************************/
    private CarePlan(Builder builder) {
        this.id          = Objects.requireNonNull(builder.id, "id == null");
        this.title       = Objects.requireNonNull(builder.title, "title == null");
        this.description = builder.description;
        this.startDate   = builder.startDate;
        this.endDate     = builder.endDate;
        this.status      = builder.status == null ? STATUS_ACTIVE : builder.status;
        this.isPremium   = builder.isPremium;
        this.tasks       = builder.tasks == null
                ? Collections.emptyList()
                : Collections.unmodifiableList(new ArrayList<>(builder.tasks));
    }

    /* ***********************************************************************
     *  Builder (recommended for constructing complex immutable objects)
     * ***********************************************************************/
    public static final class Builder {
        private @NonNull String id;
        private @NonNull String title;
        private @Nullable String description;
        private @Nullable LocalDate startDate;
        private @Nullable LocalDate endDate;
        private @Nullable String status;
        private boolean isPremium;
        private List<CareTask> tasks;

        public Builder(@NonNull String id, @NonNull String title) {
            this.id    = id;
            this.title = title;
        }

        public Builder description(@Nullable String description) {
            this.description = description; return this;
        }

        public Builder startDate(@Nullable LocalDate startDate) {
            this.startDate = startDate; return this;
        }

        public Builder endDate(@Nullable LocalDate endDate) {
            this.endDate = endDate; return this;
        }

        public Builder status(@NonNull String status) {
            this.status = status; return this;
        }

        public Builder isPremium(boolean premium) {
            this.isPremium = premium; return this;
        }

        public Builder tasks(@Nullable List<CareTask> tasks) {
            this.tasks = tasks; return this;
        }

        public CarePlan build() {
            return new CarePlan(this);
        }
    }

    /* ***********************************************************************
     *  Model Logic
     * ***********************************************************************/
    /**
     * Calculates the percentage of tasks that have been completed.
     *
     * @return value in the range [0, 100]
     */
    public int getCompletionPercentage() {
        if (tasks.isEmpty()) return 0;
        int completed = 0;
        for (CareTask task : tasks) {
            if (task.isCompleted()) completed++;
        }
        return (int) Math.round((completed * 100.0) / tasks.size());
    }

    /**
     * Returns whether the plan is currently active.
     */
    public boolean isActive() {
        return STATUS_ACTIVE.equals(status);
    }

    /**
     * Performs basic validation of the entity.
     * @throws IllegalStateException if validation fails
     */
    public void validate() {
        if (endDate != null && startDate != null && endDate.isBefore(startDate)) {
            throw new IllegalStateException("endDate must be on or after startDate");
        }
        if (!STATUS_ACTIVE.equals(status) &&
            !STATUS_PAUSED.equals(status) &&
            !STATUS_ARCHIVED.equals(status)) {
            throw new IllegalStateException("Unknown status: " + status);
        }
    }

    /* ***********************************************************************
     *  Parcelable implementation
     * ***********************************************************************/
    protected CarePlan(Parcel in) {
        id          = Objects.requireNonNull(in.readString());
        title       = Objects.requireNonNull(in.readString());
        description = in.readString();
        startDate   = (LocalDate) in.readSerializable();
        endDate     = (LocalDate) in.readSerializable();
        status      = in.readString();
        isPremium   = in.readByte() != 0;
        tasks       = new ArrayList<>();
        in.readTypedList(tasks, CareTask.CREATOR);
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeString(id);
        dest.writeString(title);
        dest.writeString(description);
        dest.writeSerializable(startDate);
        dest.writeSerializable(endDate);
        dest.writeString(status);
        dest.writeByte((byte) (isPremium ? 1 : 0));
        dest.writeTypedList(tasks);
    }

    @Override
    public int describeContents() { return 0; }

    public static final Creator<CarePlan> CREATOR = new Creator<CarePlan>() {
        @Override public CarePlan createFromParcel(Parcel in) { return new CarePlan(in); }
        @Override public CarePlan[] newArray(int size) { return new CarePlan[size]; }
    };

    /* ***********************************************************************
     *  Auto-generated equals / hashCode / toString
     * ***********************************************************************/
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof CarePlan)) return false;
        CarePlan carePlan = (CarePlan) o;
        return isPremium == carePlan.isPremium &&
                id.equals(carePlan.id) &&
                title.equals(carePlan.title) &&
                Objects.equals(description, carePlan.description) &&
                Objects.equals(startDate, carePlan.startDate) &&
                Objects.equals(endDate, carePlan.endDate) &&
                Objects.equals(status, carePlan.status) &&
                tasks.equals(carePlan.tasks);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, title, description, startDate, endDate, status, isPremium, tasks);
    }

    @Override
    public String toString() {
        return "CarePlan{" +
                "id='" + id + '\'' +
                ", title='" + title + '\'' +
                ", description='" + description + '\'' +
                ", startDate=" + startDate +
                ", endDate=" + endDate +
                ", status='" + status + '\'' +
                ", isPremium=" + isPremium +
                ", tasks=" + tasks +
                '}';
    }

    /* ***********************************************************************
     *  Getters (immutable object – no setters)
     * ***********************************************************************/
    @NonNull public String getId() { return id; }
    @NonNull public String getTitle() { return title; }
    @Nullable public String getDescription() { return description; }
    @Nullable public LocalDate getStartDate() { return startDate; }
    @Nullable public LocalDate getEndDate() { return endDate; }
    @NonNull public String getStatus() { return status; }
    public boolean isPremium() { return isPremium; }
    @NonNull public List<CareTask> getTasks() { return tasks; }

    /* ***********************************************************************
     *  Nested model – kept lightweight to avoid additional files for brevity
     * ***********************************************************************/
    @JsonClass(generateAdapter = true)
    public static final class CareTask implements Parcelable {
        @Json(name = "id")        private final String id;
        @Json(name = "title")     private final String title;
        @Json(name = "completed") private final boolean completed;

        public CareTask(String id, String title, boolean completed) {
            this.id        = Objects.requireNonNull(id, "id == null");
            this.title     = Objects.requireNonNull(title, "title == null");
            this.completed = completed;
        }

        protected CareTask(Parcel in) {
            id        = Objects.requireNonNull(in.readString());
            title     = Objects.requireNonNull(in.readString());
            completed = in.readByte() != 0;
        }

        @Override public void writeToParcel(Parcel dest, int flags) {
            dest.writeString(id);
            dest.writeString(title);
            dest.writeByte((byte) (completed ? 1 : 0));
        }

        @Override public int describeContents() { return 0; }

        public static final Creator<CareTask> CREATOR = new Creator<CareTask>() {
            @Override public CareTask createFromParcel(Parcel in) { return new CareTask(in); }
            @Override public CareTask[] newArray(int size) { return new CareTask[size]; }
        };

        public boolean isCompleted() { return completed; }
        public String getId() { return id; }
        public String getTitle() { return title; }

        @Override public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof CareTask)) return false;
            CareTask careTask = (CareTask) o;
            return completed == careTask.completed &&
                    id.equals(careTask.id) &&
                    title.equals(careTask.title);
        }

        @Override public int hashCode() {
            return Objects.hash(id, title, completed);
        }

        @Override public String toString() {
            return "CareTask{" +
                    "id='" + id + '\'' +
                    ", title='" + title + '\'' +
                    ", completed=" + completed +
                    '}';
        }
    }
}