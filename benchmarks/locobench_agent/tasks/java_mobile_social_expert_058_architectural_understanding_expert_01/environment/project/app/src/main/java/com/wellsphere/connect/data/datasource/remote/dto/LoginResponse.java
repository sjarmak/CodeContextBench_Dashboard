package com.wellsphere.connect.data.datasource.remote.dto;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.google.gson.Gson;
import com.google.gson.JsonParseException;
import com.google.gson.annotations.SerializedName;

import java.io.Serializable;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

/**
 * DTO representing the server response of a successful login request.
 * <p>
 * The object is:
 * • Immutable – all fields are final and set by constructor only. <br>
 * • Parcelable – so that it can be placed in an Intent/Bundle if necessary. <br>
 * • Serializable – to gracefully fall back when reflection-based libraries
 *   (e.g. crash reporters) attempt to serialize the object. <br>
 * • Gson-friendly – annotated with {@link SerializedName}. <br>
 *
 * Mapping from this DTO to a domain-layer object is intentionally kept outside
 * of the DTO to adhere to Clean Architecture boundaries. See
 * {@code AuthSessionMapper} in the domain module for details.
 */
@SuppressWarnings("WeakerAccess") // Fields are accessed reflectively by Gson.
public final class LoginResponse implements Parcelable, Serializable {

    private static final long serialVersionUID = 42L;

    /**
     * The primary bearer token that authorizes API calls.
     */
    @SerializedName("access_token")
    @NonNull
    private final String accessToken;

    /**
     * Token used to refresh an expired {@link #accessToken}.
     * May be {@code null} if server does not support refresh.
     */
    @SerializedName("refresh_token")
    @Nullable
    private final String refreshToken;

    /**
     * Amount of seconds after which {@link #accessToken} expires.
     */
    @SerializedName("expires_in")
    private final long expiresInSeconds;

    /**
     * ISO-8601 timestamp (UTC) representing server time at login.
     * Useful for calculating token skew on the client side.
     */
    @SerializedName("server_time_utc")
    @Nullable
    private final String serverTimeUtc;

    /**
     * Minimal subset of the user object needed at login time.
     * The full profile will be fetched lazily.
     */
    @SerializedName("user")
    @NonNull
    private final UserDto user;

    /**
     * Indicates whether Two-Factor Authentication is enabled for the account.
     * If {@code true}, mobile app should require additional challenge on next login.
     */
    @SerializedName("two_factor_enabled")
    private final boolean twoFactorEnabled;

    /* -------------------------  ctor / factory  ------------------------- */

    private LoginResponse(
            @NonNull String accessToken,
            @Nullable String refreshToken,
            long expiresInSeconds,
            @Nullable String serverTimeUtc,
            @NonNull UserDto user,
            boolean twoFactorEnabled
    ) {
        if (accessToken.isEmpty()) {
            throw new IllegalArgumentException("accessToken must not be empty.");
        }
        if (expiresInSeconds <= 0L) {
            throw new IllegalArgumentException("expiresInSeconds must be positive.");
        }
        this.accessToken = accessToken;
        this.refreshToken = refreshToken;
        this.expiresInSeconds = expiresInSeconds;
        this.serverTimeUtc = serverTimeUtc;
        this.user = Objects.requireNonNull(user, "user");
        this.twoFactorEnabled = twoFactorEnabled;
    }

    /**
     * Creates an instance from a JSON string produced by the backend.
     *
     * @throws JsonParseException if JSON is malformed or mandatory fields are missing.
     */
    @NonNull
    public static LoginResponse fromJson(@NonNull String json) {
        try {
            LoginResponse dto = new Gson().fromJson(json, LoginResponse.class);
            // Perform null-checks that Gson skips
            if (dto == null) {
                throw new JsonParseException("LoginResponse is null");
            }
            return dto;
        } catch (RuntimeException ex) {
            // Wrap any Gson runtime exceptions into JsonParseException for consistency
            throw new JsonParseException("Unable to deserialize LoginResponse", ex);
        }
    }

    /* -------------------------  getters  ------------------------- */

    @NonNull
    public String getAccessToken() {
        return accessToken;
    }

    @Nullable
    public String getRefreshToken() {
        return refreshToken;
    }

    public long getExpiresInSeconds() {
        return expiresInSeconds;
    }

    public long getExpiresInMillis() {
        return TimeUnit.SECONDS.toMillis(expiresInSeconds);
    }

    @Nullable
    public String getServerTimeUtc() {
        return serverTimeUtc;
    }

    @NonNull
    public UserDto getUser() {
        return user;
    }

    public boolean isTwoFactorEnabled() {
        return twoFactorEnabled;
    }

    /* -------------------------  Parcelable  ------------------------- */

    private LoginResponse(Parcel in) {
        accessToken = Objects.requireNonNull(in.readString());
        refreshToken = in.readString();
        expiresInSeconds = in.readLong();
        serverTimeUtc = in.readString();
        user = Objects.requireNonNull(in.readParcelable(UserDto.class.getClassLoader()));
        twoFactorEnabled = in.readByte() != 0;
    }

    @Override
    public void writeToParcel(@NonNull Parcel dest, int flags) {
        dest.writeString(accessToken);
        dest.writeString(refreshToken);
        dest.writeLong(expiresInSeconds);
        dest.writeString(serverTimeUtc);
        dest.writeParcelable(user, flags);
        dest.writeByte((byte) (twoFactorEnabled ? 1 : 0));
    }

    @Override
    public int describeContents() {
        return 0;
    }

    @NonNull
    public static final Creator<LoginResponse> CREATOR = new Creator<LoginResponse>() {
        @Override
        public LoginResponse createFromParcel(@NonNull Parcel in) {
            return new LoginResponse(in);
        }

        @Override
        public LoginResponse[] newArray(int size) {
            return new LoginResponse[size];
        }
    };

    /* -------------------------  equals / hash / toString  ------------------------- */

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof LoginResponse)) return false;
        LoginResponse that = (LoginResponse) o;
        return expiresInSeconds == that.expiresInSeconds &&
                twoFactorEnabled == that.twoFactorEnabled &&
                accessToken.equals(that.accessToken) &&
                Objects.equals(refreshToken, that.refreshToken) &&
                Objects.equals(serverTimeUtc, that.serverTimeUtc) &&
                user.equals(that.user);
    }

    @Override
    public int hashCode() {
        return Objects.hash(accessToken, refreshToken, expiresInSeconds, serverTimeUtc, user, twoFactorEnabled);
    }

    @Override
    public String toString() {
        return "LoginResponse{" +
                "accessTokenHash=" + accessToken.hashCode() + // Avoid leaking token
                ", refreshTokenPresent=" + (refreshToken != null) +
                ", expiresInSeconds=" + expiresInSeconds +
                ", serverTimeUtc='" + serverTimeUtc + '\'' +
                ", user=" + user +
                ", twoFactorEnabled=" + twoFactorEnabled +
                '}';
    }

    /* -------------------------  internal DTOs  ------------------------- */

    /**
     * Lightweight user representation included in the login payload.
     * Only essential fields are present to avoid bloating the response.
     */
    public static final class UserDto implements Parcelable, Serializable {

        private static final long serialVersionUID = 43L;

        @SerializedName("id")
        private final long id;

        @SerializedName("username")
        @NonNull
        private final String username;

        @SerializedName("display_name")
        @Nullable
        private final String displayName;

        @SerializedName("avatar_url")
        @Nullable
        private final String avatarUrl;

        private UserDto(long id,
                        @NonNull String username,
                        @Nullable String displayName,
                        @Nullable String avatarUrl) {
            this.id = id;
            this.username = Objects.requireNonNull(username, "username");
            this.displayName = displayName;
            this.avatarUrl = avatarUrl;
        }

        public long getId() {
            return id;
        }

        @NonNull
        public String getUsername() {
            return username;
        }

        @Nullable
        public String getDisplayName() {
            return displayName;
        }

        @Nullable
        public String getAvatarUrl() {
            return avatarUrl;
        }

        /* Parcelable impl */

        protected UserDto(Parcel in) {
            id = in.readLong();
            username = Objects.requireNonNull(in.readString());
            displayName = in.readString();
            avatarUrl = in.readString();
        }

        @Override
        public void writeToParcel(@NonNull Parcel dest, int flags) {
            dest.writeLong(id);
            dest.writeString(username);
            dest.writeString(displayName);
            dest.writeString(avatarUrl);
        }

        @Override
        public int describeContents() {
            return 0;
        }

        @NonNull
        public static final Creator<UserDto> CREATOR = new Creator<UserDto>() {
            @Override
            public UserDto createFromParcel(@NonNull Parcel in) {
                return new UserDto(in);
            }

            @Override
            public UserDto[] newArray(int size) {
                return new UserDto[size];
            }
        };

        /* equals / hash / toString */

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof UserDto)) return false;
            UserDto userDto = (UserDto) o;
            return id == userDto.id &&
                    username.equals(userDto.username) &&
                    Objects.equals(displayName, userDto.displayName) &&
                    Objects.equals(avatarUrl, userDto.avatarUrl);
        }

        @Override
        public int hashCode() {
            return Objects.hash(id, username, displayName, avatarUrl);
        }

        @Override
        public String toString() {
            return "UserDto{" +
                    "id=" + id +
                    ", username='" + username + '\'' +
                    ", displayName='" + displayName + '\'' +
                    ", avatarUrl='" + avatarUrl + '\'' +
                    '}';
        }
    }
}