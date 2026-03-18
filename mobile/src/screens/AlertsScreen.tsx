import React, { useState, useCallback } from "react";
import { View, Text, ScrollView, StyleSheet, RefreshControl } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { getBrand } from "../config/branding";
import { api } from "../api/client";

export function AlertsScreen() {
  const brand = getBrand();
  const [alerts, setAlerts] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadAlerts = useCallback(async () => {
    try {
      const data = await api.getAlertHistory();
      setAlerts(data);
    } catch {}
  }, []);

  useFocusEffect(useCallback(() => { loadAlerts(); }, [loadAlerts]));

  async function onRefresh() {
    setRefreshing(true);
    await loadAlerts();
    setRefreshing(false);
  }

  const severityColor = (s: string) => {
    if (s === "high") return brand.errorColor;
    if (s === "medium") return brand.warningColor;
    return brand.textSecondary;
  };

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: brand.backgroundColor }]}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={brand.primaryColor} />}
    >
      <Text style={[styles.title, { color: brand.textColor }]}>Alerts</Text>

      {alerts.length === 0 ? (
        <View style={[styles.empty, { backgroundColor: brand.surfaceColor }]}>
          <Text style={[styles.emptyText, { color: brand.textSecondary }]}>No alerts today.</Text>
        </View>
      ) : (
        alerts.map((alert, i) => {
          const event = alert.event || {};
          return (
            <View key={i} style={[styles.card, { backgroundColor: brand.surfaceColor }]}>
              <View style={styles.cardHeader}>
                <View style={[styles.badge, { backgroundColor: severityColor(event.severity) + "20" }]}>
                  <Text style={[styles.badgeText, { color: severityColor(event.severity) }]}>
                    {(event.type || "").replace(/_/g, " ")}
                  </Text>
                </View>
                <Text style={[styles.time, { color: brand.textSecondary }]}>
                  {alert.fired_at ? new Date(alert.fired_at * 1000).toLocaleTimeString() : ""}
                </Text>
              </View>
              <Text style={[styles.desc, { color: brand.textColor }]}>{event.description || ""}</Text>
              <Text style={[styles.rule, { color: brand.textSecondary }]}>Rule: {alert.rule_name || "N/A"}</Text>
            </View>
          );
        })
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  title: { fontSize: 20, fontWeight: "700", padding: 20, paddingTop: 60 },
  empty: { margin: 20, borderRadius: 12, padding: 40, alignItems: "center" },
  emptyText: { textAlign: "center", fontSize: 13 },
  card: { marginHorizontal: 16, marginBottom: 8, borderRadius: 12, padding: 14 },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  badgeText: { fontSize: 11, fontWeight: "600", textTransform: "capitalize" },
  time: { fontSize: 11 },
  desc: { fontSize: 13, marginBottom: 4 },
  rule: { fontSize: 11 },
});
