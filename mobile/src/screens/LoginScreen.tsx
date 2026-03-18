import React, { useState, useEffect } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, Alert,
} from "react-native";
import { getBrand } from "../config/branding";
import { api } from "../api/client";

interface Props {
  onLogin: () => void;
}

export function LoginScreen({ onLogin }: Props) {
  const brand = getBrand();
  const [username, setUsername] = useState("");
  const [pin, setPin] = useState("");
  const [setupMode, setSetupMode] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkStatus();
  }, []);

  async function checkStatus() {
    try {
      const status = await api.checkStatus();
      setSetupMode(status.setup_required);
    } catch (e: any) {
      Alert.alert("Connection Error", `Cannot reach server at ${brand.apiBaseUrl}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    if (!username.trim() || pin.length < 4) {
      Alert.alert("Error", "Username required, PIN must be 4+ characters");
      return;
    }
    setLoading(true);
    try {
      if (setupMode) {
        await api.setup(username.trim(), pin);
      } else {
        await api.login(username.trim(), pin);
      }
      onLogin();
    } catch (e: any) {
      Alert.alert("Login Failed", e.message || "Invalid credentials");
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: brand.backgroundColor }]}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.logoContainer}>
        <View style={[styles.logoMark, { backgroundColor: brand.primaryColor }]}>
          <Text style={styles.logoText}>{brand.logoText}</Text>
        </View>
        <Text style={[styles.appName, { color: brand.textColor }]}>{brand.appName}</Text>
        <Text style={[styles.tagline, { color: brand.textSecondary }]}>{brand.tagline}</Text>
      </View>

      <View style={[styles.form, { backgroundColor: brand.surfaceColor }]}>
        <Text style={[styles.formTitle, { color: brand.textColor }]}>
          {setupMode ? "First-Time Setup" : "Sign In"}
        </Text>
        {setupMode && (
          <Text style={[styles.formSubtitle, { color: brand.textSecondary }]}>
            Create your admin account to get started.
          </Text>
        )}

        <TextInput
          style={[styles.input, { backgroundColor: brand.backgroundColor, color: brand.textColor, borderColor: brand.textSecondary + "40" }]}
          placeholder="Username"
          placeholderTextColor={brand.textSecondary}
          value={username}
          onChangeText={setUsername}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TextInput
          style={[styles.input, { backgroundColor: brand.backgroundColor, color: brand.textColor, borderColor: brand.textSecondary + "40" }]}
          placeholder="PIN"
          placeholderTextColor={brand.textSecondary}
          value={pin}
          onChangeText={setPin}
          secureTextEntry
          keyboardType="number-pad"
        />

        <TouchableOpacity
          style={[styles.button, { backgroundColor: brand.primaryColor, opacity: loading ? 0.6 : 1 }]}
          onPress={handleSubmit}
          disabled={loading}
        >
          <Text style={styles.buttonText}>
            {loading ? "..." : setupMode ? "Create Admin Account" : "Sign In"}
          </Text>
        </TouchableOpacity>
      </View>

      {brand.hipaaEnabled && (
        <View style={[styles.hipaaNotice, { borderColor: brand.warningColor + "40" }]}>
          <Text style={[styles.hipaaText, { color: brand.warningColor }]}>
            HIPAA Notice: This system processes PHI. All access is logged.
          </Text>
        </View>
      )}

      {brand.showPoweredBy && (
        <Text style={[styles.poweredBy, { color: brand.textSecondary }]}>Powered by The I</Text>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24 },
  logoContainer: { alignItems: "center", marginBottom: 32 },
  logoMark: { width: 64, height: 64, borderRadius: 16, justifyContent: "center", alignItems: "center", marginBottom: 12 },
  logoText: { color: "#fff", fontSize: 28, fontWeight: "800" },
  appName: { fontSize: 24, fontWeight: "700" },
  tagline: { fontSize: 14, marginTop: 4 },
  form: { borderRadius: 16, padding: 20 },
  formTitle: { fontSize: 16, fontWeight: "600", marginBottom: 4 },
  formSubtitle: { fontSize: 12, marginBottom: 16 },
  input: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 14, marginBottom: 12 },
  button: { borderRadius: 10, paddingVertical: 14, alignItems: "center", marginTop: 4 },
  buttonText: { color: "#fff", fontSize: 14, fontWeight: "600" },
  hipaaNotice: { marginTop: 16, borderWidth: 1, borderRadius: 10, padding: 12 },
  hipaaText: { fontSize: 11, textAlign: "center" },
  poweredBy: { textAlign: "center", marginTop: 16, fontSize: 11 },
});
