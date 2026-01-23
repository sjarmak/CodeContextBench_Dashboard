package com.wellsphere.connect.data.datasource.remote.dto;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.google.gson.Gson;
import com.google.gson.JsonSyntaxException;
import com.google.gson.annotations.SerializedName;

import java.io.IOException;
import java.io.Serializable;
import java.util.Objects;

import okhttp3.ResponseBody;
import retrofit2.Response;

/**
 * Generic network response envelope used by the data-layer.
 * <p>
 * All responses coming from the WellSphere Connect public API are expected to have
 * a common shape similar to:
 *
 * <pre>
 * {
 *   "status"     : 200,
 *   "success"    : true,
 *   "message"    : "OK",
 *   "data"       : { ... },
 *   "pagination" : { ... },
 *   "error"      : { ... }
 * }
 * </pre>
 *
 * @param <T> The concrete payload type for the response.
 */
@SuppressWarnings("WeakerAccess")
public final class ApiResponse<T> implements Serializable {

    private static final long serialVersionUID = 43L;
    private static final Gson GSON = new Gson();

    // ------------------------------------------------------------------------
    // Fields mapped from JSON
    // ------------------------------------------------------------------------

    /**
     * HTTP status code — mirrors {@code retrofit2.Response.code()}.
     */
    @SerializedName("status")
    private final int statusCode;

    /**
     * True when the request was successful from the server perspective.
     */
    @SerializedName("success")
    private final boolean success;

    /**
     * Human-readable status or error message.
     */
    @SerializedName("message")
    @Nullable
    private final String message;

    /**
     * Actual business payload. Can be {@code null} for certain responses.
     */
    @SerializedName("data")
    @Nullable
    private final T data;

    /**
     * Optional pagination metadata when the endpoint returns a collection.
     */
    @SerializedName("pagination")
    @Nullable
    private final Pagination pagination;

    /**
     * Optional error description when {@link #success} is {@code false}.
     */
    @SerializedName("error")
    @Nullable
    private final ApiError error;

    // ------------------------------------------------------------------------
    // Construction
    // ------------------------------------------------------------------------

    private ApiResponse(Builder<T> builder) {
        this.statusCode = builder.statusCode;
        this.success = builder.success;
        this.message = builder.message;
        this.data = builder.data;
        this.pagination = builder.pagination;
        this.error = builder.error;
    }

    /**
     * Creates an {@link ApiResponse} instance based on a {@link retrofit2.Response}
     * coming from Retrofit. This method never throws; conversion issues are stored
     * into the {@link #error} field instead.
     */
    public static <T> ApiResponse<T> fromRetrofit(@NonNull Response<T> retrofitResponse) {
        Builder<T> builder = builder();

        builder.statusCode(retrofitResponse.code())
               .success(retrofitResponse.isSuccessful())
               .message(retrofitResponse.message());

        if (retrofitResponse.isSuccessful()) {
            builder.data(retrofitResponse.body());
        } else {
            builder.error(parseErrorBody(retrofitResponse.errorBody()));
        }

        return builder.build();
    }

    // ------------------------------------------------------------------------
    // Public helpers
    // ------------------------------------------------------------------------

    /**
     * Convenience accessor that either returns the payload or throws a
     * domain-specific {@link ApiException} if the response represents a failure.
     */
    @Nullable
    public T getOrThrow() {
        if (success) {
            return data;
        }
        throw new ApiException(
                statusCode,
                message != null ? message : "Unknown API error",
                error
        );
    }

    public boolean isSuccessful() {
        return success;
    }

    @Nullable
    public T getData() {
        return data;
    }

    @Nullable
    public String getMessage() {
        return message;
    }

    public int getStatusCode() {
        return statusCode;
    }

    @Nullable
    public Pagination getPagination() {
        return pagination;
    }

    @Nullable
    public ApiError getError() {
        return error;
    }

    // ------------------------------------------------------------------------
    // Object overrides
    // ------------------------------------------------------------------------

    @Override
    public String toString() {
        return "ApiResponse{" +
               "statusCode=" + statusCode +
               ", success=" + success +
               ", message='" + message + '\'' +
               ", data=" + data +
               ", pagination=" + pagination +
               ", error=" + error +
               '}';
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof ApiResponse)) return false;
        ApiResponse<?> that = (ApiResponse<?>) o;
        return statusCode == that.statusCode &&
               success == that.success &&
               Objects.equals(message, that.message) &&
               Objects.equals(data, that.data) &&
               Objects.equals(pagination, that.pagination) &&
               Objects.equals(error, that.error);
    }

    @Override
    public int hashCode() {
        return Objects.hash(statusCode, success, message, data, pagination, error);
    }

    // ------------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------------

    @Nullable
    private static ApiError parseErrorBody(@Nullable ResponseBody errorBody) {
        if (errorBody == null) {
            return null;
        }

        try {
            String raw = errorBody.string();
            // Attempt to parse a well-shaped error response coming from backend.
            return GSON.fromJson(raw, ApiError.class);
        } catch (IOException | JsonSyntaxException ignored) {
            // Either I/O failed or the backend gave us something unexpected;
            // fallback to a generic error.
            return new ApiError.Builder()
                    .code("UNPARSEABLE_ERROR")
                    .message("Unable to parse error response from server.")
                    .build();
        } finally {
            try {
                errorBody.close();
            } catch (Exception ignored) {
            }
        }
    }

    // ------------------------------------------------------------------------
    // Builder
    // ------------------------------------------------------------------------

    public static <T> Builder<T> builder() {
        return new Builder<>();
    }

    public static final class Builder<T> {
        private int statusCode;
        private boolean success;
        private String message;
        private T data;
        private Pagination pagination;
        private ApiError error;

        public Builder<T> statusCode(int statusCode) {
            this.statusCode = statusCode;
            return this;
        }

        public Builder<T> success(boolean success) {
            this.success = success;
            return this;
        }

        public Builder<T> message(@Nullable String message) {
            this.message = message;
            return this;
        }

        public Builder<T> data(@Nullable T data) {
            this.data = data;
            return this;
        }

        public Builder<T> pagination(@Nullable Pagination pagination) {
            this.pagination = pagination;
            return this;
        }

        public Builder<T> error(@Nullable ApiError error) {
            this.error = error;
            return this;
        }

        public ApiResponse<T> build() {
            return new ApiResponse<>(this);
        }
    }

    // ------------------------------------------------------------------------
    // Nested DTOs
    // ------------------------------------------------------------------------

    /**
     * Pagination metadata returned by list endpoints.
     */
    public static final class Pagination implements Serializable {

        private static final long serialVersionUID = 44L;

        @SerializedName("page")
        private final int page;

        @SerializedName("per_page")
        private final int perPage;

        @SerializedName("total_pages")
        private final int totalPages;

        @SerializedName("total_items")
        private final long totalItems;

        public Pagination(int page, int perPage, int totalPages, long totalItems) {
            this.page = page;
            this.perPage = perPage;
            this.totalPages = totalPages;
            this.totalItems = totalItems;
        }

        public int getPage() {
            return page;
        }

        public int getPerPage() {
            return perPage;
        }

        public int getTotalPages() {
            return totalPages;
        }

        public long getTotalItems() {
            return totalItems;
        }

        @Override
        public String toString() {
            return "Pagination{" +
                   "page=" + page +
                   ", perPage=" + perPage +
                   ", totalPages=" + totalPages +
                   ", totalItems=" + totalItems +
                   '}';
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof Pagination)) return false;
            Pagination that = (Pagination) o;
            return page == that.page &&
                   perPage == that.perPage &&
                   totalPages == that.totalPages &&
                   totalItems == that.totalItems;
        }

        @Override
        public int hashCode() {
            return Objects.hash(page, perPage, totalPages, totalItems);
        }
    }

    /**
     * Structured error coming from backend.
     */
    public static final class ApiError implements Serializable {

        private static final long serialVersionUID = 45L;

        @SerializedName("code")
        private final String code;

        @SerializedName("message")
        private final String message;

        @SerializedName("details")
        @Nullable
        private final Object details;

        private ApiError(Builder builder) {
            this.code = builder.code;
            this.message = builder.message;
            this.details = builder.details;
        }

        @Nullable
        public Object getDetails() {
            return details;
        }

        public String getCode() {
            return code;
        }

        public String getMessage() {
            return message;
        }

        @Override
        public String toString() {
            return "ApiError{" +
                   "code='" + code + '\'' +
                   ", message='" + message + '\'' +
                   ", details=" + details +
                   '}';
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof ApiError)) return false;
            ApiError apiError = (ApiError) o;
            return Objects.equals(code, apiError.code) &&
                   Objects.equals(message, apiError.message) &&
                   Objects.equals(details, apiError.details);
        }

        @Override
        public int hashCode() {
            return Objects.hash(code, message, details);
        }

        // --------------------------------------------------------------------
        // Builder
        // --------------------------------------------------------------------

        public static class Builder {
            private String code;
            private String message;
            private Object details;

            public Builder code(@NonNull String code) {
                this.code = code;
                return this;
            }

            public Builder message(@NonNull String message) {
                this.message = message;
                return this;
            }

            public Builder details(@Nullable Object details) {
                this.details = details;
                return this;
            }

            public ApiError build() {
                return new ApiError(this);
            }
        }
    }

    // ------------------------------------------------------------------------
    // Exception
    // ------------------------------------------------------------------------

    /**
     * Runtime exception representing an unsuccessful API call. This may be
     * caught at the Repository layer and mapped to domain-specific failures.
     */
    public static class ApiException extends RuntimeException {

        private final int httpStatus;
        @Nullable
        private final ApiError apiError;

        public ApiException(int httpStatus, @NonNull String message, @Nullable ApiError apiError) {
            super(message);
            this.httpStatus = httpStatus;
            this.apiError = apiError;
        }

        public int getHttpStatus() {
            return httpStatus;
        }

        @Nullable
        public ApiError getApiError() {
            return apiError;
        }
    }
}