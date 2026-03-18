import React, { useState } from "react";
import {
  View, Text, TextInput, ScrollView, StyleSheet,
  TouchableOpacity, Keyboard,
} from "react-native";
import { getBrand } from "../config/branding";
import { api } from "../api/client";

export function SearchScreen() {
  const brand = getBrand();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [searching, setSearching] = useState(false);

  async function handleSearch() {
    if (!query.trim()) return;
    Keyboard.dismiss();
    setSearching(true);
    try {
      const data = await api.search(query.trim());
      setResults(data.results || []);
      setTotal(data.total || 0);
    } catch {}
    setSearching(false);
  }

  const severityColor = (s: string) => {
    if (s === "high") return brand.errorColor;
    if (s === "medium") return brand.warningColor;
    return brand.textSecondary;
  };

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: brand.backgroundColor }]}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={[styles.title, { color: brand.textColor }]}>Search</Text>

      <View style={[styles.searchBar, { backgroundColor: brand.surfaceColor }]}>
        <TextInput
          style={[styles.input, { color: brand.textColor }]}
          placeholder='e.g., "show me all falls", "find loitering"'
          placeholderTextColor={brand.textSecondary}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={handleSearch}
          returnKeyType="search"
        />
        <TouchableOpacity
          style={[styles.searchBtn, { backgroundColor: brand.primaryColor }]}
          onPress={handleSearch}
        >
          <Text style={styles.searchBtnText}>{searching ? "..." : "Search"}</Text>
        </TouchableOpacity>
      </View>

      {total > 0 && (
        <Text style={[styles.resultCount, { color: brand.textSecondary }]}>
          {total} result{total !== 1 ? "s" : ""}
        </Text>
      )}

      {results.map((r, i) => (
        <View key={i} style={[styles.card, { backgroundColor: brand.surfaceColor }]}>
          <View style={styles.cardHeader}>
            <View style={[styles.badge, { backgroundColor: severityColor(r.severity) + "20" }]}>
              <Text style={[styles.badgeText, { color: severityColor(r.severity) }]}>
                {(r.event_type || "").replace(/_/g, " ")}
              </Text>
            </View>
            <Text style={[styles.domain, { color: brand.accentColor }]}>{r.domain}</Text>
          </View>
          <Text style={[styles.desc, { color: brand.textColor }]}>{r.description}</Text>
          {r.person_name ? (
            <Text style={[styles.person, { color: brand.textSecondary }]}>Person: {r.person_name}</Text>
          ) : null}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  title: { fontSize: 20, fontWeight: "700", padding: 20, paddingTop: 60 },
  searchBar: { flexDirection: "row", marginHorizontal: 16, borderRadius: 12, overflow: "hidden", marginBottom: 12 },
  input: { flex: 1, paddingHorizontal: 14, paddingVertical: 12, fontSize: 14 },
  searchBtn: { paddingHorizontal: 16, justifyContent: "center" },
  searchBtnText: { color: "#fff", fontWeight: "600", fontSize: 13 },
  resultCount: { paddingHorizontal: 20, fontSize: 12, marginBottom: 8 },
  card: { marginHorizontal: 16, marginBottom: 8, borderRadius: 12, padding: 14 },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  badgeText: { fontSize: 11, fontWeight: "600", textTransform: "capitalize" },
  domain: { fontSize: 11, fontWeight: "500" },
  desc: { fontSize: 13 },
  person: { fontSize: 11, marginTop: 4 },
});
