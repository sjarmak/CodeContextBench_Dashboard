```java
package com.wellsphere.connect.data.datasource.remote.dto;

import android.os.Parcel;
import android.os.Parcelable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.google.gson.annotations.SerializedName;

import java.io.Serializable;
import java.nio.charset.StandardCharsets;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.security.spec.InvalidKeySpecException;
import java.util.Base64;
import java.util.Objects;
import java.util.UUID;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

/**
 * Immutable Data-Transfer-Object that encapsulates a login request dispatched to the
 * WellSphere authentication service.
 *
 * Production-quality highlights:
 * • Builder pattern with mandatory-field validation
 * • Optional PBKDF2 password hashing through {@link Builder#rawPassword(String)}
 * • Parcelable & Serializable — survives configuration changes and process death
 * • Hardened equals()/hashCode()/toString() implementations
 *
 * NOTE: The {@code passwordHash} field is intentionally not printed in {@link #toString()}
 * to avoid leaking secrets to logcat or crash reports.
 */
@SuppressWarnings("unused") // Members are accessed via reflection by GSON & Android runtime.
public final class LoginRequest implements Parcelable, Serializable {

    private static final long serialVersionUID = 0xFACADE;

    // --------------- Network payload fields -----------------

    @SerializedName("username_or_email")
    private final String usernameOrEmail;

    @SerializedName("secret")                 // Already PBKDF2-encoded before transit
    private final String passwordHash;

    @SerializedName("device_id")              // Android-wide device UUID (not hardware id)
    private final String deviceId;

    @SerializedName("push_token")             // FCM or Huawei token (optional)
    @Nullable
    private final String pushToken;

    @SerializedName("biometric_enabled")
    private final boolean biometricEnabled;

    @SerializedName("app_build")              // e.g. 342
    private final int appBuild;

    @SerializedName("app_version")            // e.g. 2.4.1
    private final String appVersion;

    // --------------- Construction -----------------

    private LoginRequest(Builder builder) {
        this.usernameOrEmail  = builder.usernameOrEmail;
        this.passwordHash     = builder.passwordHash;
        this.deviceId         = builder.deviceId;
        this.pushToken        = builder.pushToken;
        this.biometricEnabled = builder.biometricEnabled;
        this.appBuild         = builder.appBuild;
        this.appVersion       = builder.appVersion;
    }

    // Parcelable boilerplate --------------------------------------------------

    private LoginRequest(Parcel in) {
        usernameOrEmail  = in.readString();
        passwordHash     = in.readString();
        deviceId         = in.readString();
        pushToken        = in.readString();
        biometricEnabled = in.readByte() != 0;
        appBuild         = in.readInt();
        appVersion       = in.readString();
    }

    public static final Creator<LoginRequest> CREATOR = new Creator<LoginRequest>() {
        @Override public LoginRequest createFromParcel(Parcel in) { return new LoginRequest(in); }
        @Override public LoginRequest[] newArray(int size)        { return new LoginRequest[size]; }
    };

    @Override public int describeContents() { return 0; }

    @Override public void writeToParcel(Parcel dest, int flags) {
        dest.writeString(usernameOrEmail);
        dest.writeString(passwordHash);
        dest.writeString(deviceId);
        dest.writeString(pushToken);
        dest.writeByte((byte) (biometricEnabled ? 1 : 0));
        dest.writeInt(appBuild);
        dest.writeString(appVersion);
    }

    // --------------- Accessors -----------------

    public String   getUsernameOrEmail() { return usernameOrEmail; }
    public String   getPasswordHash()    { return passwordHash; }
    public String   getDeviceId()        { return deviceId; }
    @Nullable public String getPushToken() { return pushToken; }
    public boolean  isBiometricEnabled() { return biometricEnabled; }
    public int      getAppBuild()        { return appBuild; }
    public String   getAppVersion()      { return appVersion; }

    // --------------- Builder -----------------

    public static final class Builder {
        private static final int    DEFAULT_APP_BUILD    = 1;
        private static final String DEFAULT_APP_VERSION  = "dev";
        private static final String DEFAULT_DEVICE_ID    = UUID.randomUUID().toString();

        private String  usernameOrEmail;
        private String  passwordHash;
        private String  deviceId        = DEFAULT_DEVICE_ID;
        private String  pushToken;
        private boolean biometricEnabled;
        private int     appBuild        = DEFAULT_APP_BUILD;
        private String  appVersion      = DEFAULT_APP_VERSION;

        /** Mandatory: user's identifier */
        public Builder usernameOrEmail(@NonNull String value) {
            this.usernameOrEmail = Objects.requireNonNull(value, "usernameOrEmail").trim();
            return this;
        }

        /**
         * Supply a client-side *hashed* secret (recommended). Use {@link #rawPassword(String)}
         * if the raw password is all you have and hashing is desired.
         */
        public Builder passwordHash(@NonNull String hash) {
            this.passwordHash = Objects.requireNonNull(hash, "passwordHash");
            return this;
        }

        /**
         * Convenience that transparently hashes the supplied raw password with PBKDF2.
         * Hashing cost is synchronous and therefore should be called off the UI thread.
         */
        public Builder rawPassword(@NonNull String rawPassword) {
            this.passwordHash = SecureHashUtils.pbkdf2(rawPassword);
            return this;
        }

        public Builder deviceId(@NonNull String value)     { this.deviceId = value; return this; }
        public Builder pushToken(@Nullable String value)   { this.pushToken = value; return this; }
        public Builder biometricEnabled(boolean enabled)   { this.biometricEnabled = enabled; return this; }
        public Builder appBuild(int build)                 { this.appBuild = build; return this; }
        public Builder appVersion(@NonNull String version) { this.appVersion = version; return this; }

        /** Finalise construction, validating mandatory fields. */
        public LoginRequest build() {
            if (usernameOrEmail == null || usernameOrEmail.isEmpty()) {
                throw new IllegalStateException("usernameOrEmail must be provided");
            }
            if (passwordHash == null || passwordHash.isEmpty()) {
                throw new IllegalStateException("Either #passwordHash or #rawPassword must be provided");
            }
            if (deviceId == null || deviceId.isEmpty()) {
                deviceId = DEFAULT_DEVICE_ID;
            }
            return new LoginRequest(this);
        }
    }

    // --------------- Utility -----------------

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof LoginRequest)) return false;
        LoginRequest that = (LoginRequest) o;
        return biometricEnabled == that.biometricEnabled &&
               appBuild == that.appBuild &&
               Objects.equals(usernameOrEmail, that.usernameOrEmail) &&
               Objects.equals(passwordHash, that.passwordHash) &&
               Objects.equals(deviceId, that.deviceId) &&
               Objects.equals(pushToken, that.pushToken) &&
               Objects.equals(appVersion, that.appVersion);
    }

    @Override
    public int hashCode() {
        return Objects.hash(usernameOrEmail, passwordHash, deviceId,
                            pushToken, biometricEnabled, appBuild, appVersion);
    }

    @Override
    public String toString() {
        return "LoginRequest{" +
               "usernameOrEmail='" + usernameOrEmail + '\'' +
               ", deviceId='" + deviceId + '\'' +
               ", pushToken=" + (pushToken != null ? "***" : null) +
               ", biometricEnabled=" + biometricEnabled +
               ", appBuild=" + appBuild +
               ", appVersion='" + appVersion + '\'' +
               '}';
    }

    // --------------- Helper class (PBKDF2 hashing) -----------------

    /**
     * Minimal PBKDF2 helper. Uses a per-hash random salt that is prefixed to the
     * returned Base64 string. Server must extract the first 16 bytes as salt.
     *
     * DISCLAIMER: For demonstration only – real-life security code must be audited.
     */
    private static final class SecureHashUtils {
        private static final String ALGORITHM   = "PBKDF2WithHmacSHA256";
        private static final int    ITERATIONS  = 12_000;
        private static final int    KEY_LENGTH  = 256;          // bits
        private static final int    SALT_LENGTH = 16;           // bytes

        @NonNull static String pbkdf2(@NonNull String password) {
            Objects.requireNonNull(password, "password");
            try {
                byte[] salt = new byte[SALT_LENGTH];
                SecureRandom.getInstanceStrong().nextBytes(salt);

                PBEKeySpec spec = new PBEKeySpec(
                        password.toCharArray(),
                        salt,
                        ITERATIONS,
                        KEY_LENGTH
                );
                SecretKeyFactory skf = SecretKeyFactory.getInstance(ALGORITHM);
                byte[] hashed = skf.generateSecret(spec).getEncoded();

                byte[] saltPlusHash = new byte[salt.length + hashed.length];
                System.arraycopy(salt, 0, saltPlusHash, 0, salt.length);
                System.arraycopy(hashed, 0, saltPlusHash, salt.length, hashed.length);

                return Base64.getEncoder().encodeToString(saltPlusHash);
            } catch (NoSuchAlgorithmException | InvalidKeySpecException ex) {
                // Infeasible on well-behaved Android runtimes; convert to unchecked for caller
                throw new IllegalStateException("Failed to PBKDF2-hash password", ex);
            }
        }
    }
}
```