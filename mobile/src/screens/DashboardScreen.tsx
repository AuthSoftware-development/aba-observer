import React, { useState, useCallback } from "react";
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity, RefreshControl,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { getBrand } from "../config/branding";
import { api } from "../api/client";

export function DashboardScreen() {
  const brand = getBrand();
  const [status, setStatus] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const s = await api.getSystemStatus();
      setStatus(s);
    } catch {}
  }, []);

  useFocusEffect(useCallback(() => { loadData(); }, [loadData]));

  async function onRefresh() {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }

  const user = api.currentUser;

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: brand.backgroundColor }]}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={brand.primaryColor} />}
    >
      <View style={styles.header}>
        <View style={[styles.logoMark, { backgroundColor: brand.primaryColor }]}>
          <Text style={styles.logoText}>{brand.logoText}</Text>
        </View>
        <View>
          <Text style={[styles.title, { color: brand.textColor }]}>{brand.appName}</Text>
          <Text style={[styles.subtitle, { color: brand.textSecondary }]}>
            {user ? `${user.username} (${user.role})` : ""}
          </Text>
        </View>
      </View>

      {status && (
        <>
          <Text style={[styles.sectionTitle, { color: brand.textColor }]}>System</Text>
          <View style={styles.cardGrid}>
            <StatCard label="Version" value={status.version} brand={brand} />
            <StatCard label="Cameras" value={`${status.cameras?.connected || 0}/${status.cameras?.total || 0}`} brand={brand} />
            <StatCard label="Events" value={status.search_index?.total_events || 0} brand={brand} />
            <StatCard label="Results" value={status.storage?.encrypted_results || 0} brand={brand} />
          </View>

          <Text style={[styles.sectionTitle, { color: brand.textColor }]}>Domains</Text>
          <View style={styles.cardGrid}>
            {Object.entries(status.domains || {}).map(([name, info]: [string, any]) => (
              <View key={name} style={[styles.card, { backgroundColor: brand.surfaceColor }]}>
                <Text style={[styles.cardLabel, { color: brand.textSecondary }]}>{name.toUpperCase()}</Text>
                <Text style={[styles.cardValue, { color: brand.successColor }]}>{info.status}</Text>
              </View>
            ))}
          </View>

          {status.resources?.cpu_percent !== undefined && (
            <>
              <Text style={[styles.sectionTitle, { color: brand.textColor }]}>Resources</Text>
              <View style={styles.cardGrid}>
                <StatCard label="CPU" value={`${status.resources.cpu_percent}%`} brand={brand} />
                <StatCard label="Memory" value={`${status.resources.memory_used_gb}/${status.resources.memory_total_gb} GB`} brand={brand} />
              </View>
            </>
          )}
        </>
      )}
    </ScrollView>
  );
}

function StatCard({ label, value, brand }: { label: string; value: any; brand: any }) {
  return (
    <View style={[styles.card, { backgroundColor: brand.surfaceColor }]}>
      <Text style={[styles.cardLabel, { color: brand.textSecondary }]}>{label}</Text>
      <Text style={[styles.cardValue, { color: brand.textColor }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: "row", alignItems: "center", gap: 12, padding: 20, paddingTop: 60 },
  logoMark: { width: 44, height: 44, borderRadius: 12, justifyContent: "center", alignItems: "center" },
  logoText: { color: "#fff", fontSize: 20, fontWeight: "800" },
  title: { fontSize: 20, fontWeight: "700" },
  subtitle: { fontSize: 12 },
  sectionTitle: { fontSize: 14, fontWeight: "600", paddingHorizontal: 20, marginTop: 20, marginBottom: 8 },
  cardGrid: { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: 16, gap: 8 },
  card: { borderRadius: 12, padding: 14, minWidth: "45%", flex: 1 },
  cardLabel: { fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 },
  cardValue: { fontSize: 18, fontWeight: "700", marginTop: 4 },
});
