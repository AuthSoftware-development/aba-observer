import React, { useState, useCallback } from "react";
import { View, Text, ScrollView, StyleSheet, RefreshControl, Image } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { getBrand } from "../config/branding";
import { api } from "../api/client";

export function CamerasScreen() {
  const brand = getBrand();
  const [cameras, setCameras] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadCameras = useCallback(async () => {
    try {
      const cams = await api.getCameras();
      setCameras(cams);
    } catch {}
  }, []);

  useFocusEffect(useCallback(() => { loadCameras(); }, [loadCameras]));

  async function onRefresh() {
    setRefreshing(true);
    await loadCameras();
    setRefreshing(false);
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: brand.backgroundColor }]}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={brand.primaryColor} />}
    >
      <Text style={[styles.title, { color: brand.textColor }]}>Cameras</Text>

      {cameras.length === 0 ? (
        <View style={[styles.empty, { backgroundColor: brand.surfaceColor }]}>
          <Text style={[styles.emptyText, { color: brand.textSecondary }]}>
            No cameras connected. Add cameras from the web dashboard.
          </Text>
        </View>
      ) : (
        cameras.map((cam) => (
          <View key={cam.camera_id} style={[styles.card, { backgroundColor: brand.surfaceColor }]}>
            <View style={styles.cardHeader}>
              <View style={styles.statusRow}>
                <View style={[styles.dot, { backgroundColor: cam.connected ? brand.successColor : brand.errorColor }]} />
                <Text style={[styles.camName, { color: brand.textColor }]}>{cam.name}</Text>
              </View>
              <Text style={[styles.fps, { color: brand.textSecondary }]}>
                {cam.connected ? `${cam.fps} fps` : "disconnected"}
              </Text>
            </View>
            <Text style={[styles.camUrl, { color: brand.textSecondary }]}>{cam.rtsp_url}</Text>
          </View>
        ))
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
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  camName: { fontSize: 14, fontWeight: "600" },
  fps: { fontSize: 12 },
  camUrl: { fontSize: 11, marginTop: 4 },
});
