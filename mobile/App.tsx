import React, { useState, useEffect } from "react";
import { StatusBar, Text, View } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import { getBrand } from "./src/config/branding";
import { api } from "./src/api/client";
import { LoginScreen } from "./src/screens/LoginScreen";
import { DashboardScreen } from "./src/screens/DashboardScreen";
import { CamerasScreen } from "./src/screens/CamerasScreen";
import { AlertsScreen } from "./src/screens/AlertsScreen";
import { SearchScreen } from "./src/screens/SearchScreen";

const Tab = createBottomTabNavigator();

function TabIcon({ name }: { name: string }) {
  const icons: Record<string, string> = {
    Dashboard: "\u25A0",
    Cameras: "\u25CB",
    Alerts: "\u25B2",
    Search: "\u2315",
  };
  return <Text style={{ fontSize: 18 }}>{icons[name] || "\u25CF"}</Text>;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const brand = getBrand();

  useEffect(() => {
    initAuth();
  }, []);

  async function initAuth() {
    await api.init();
    if (api.isAuthenticated) {
      try {
        await api.refreshToken();
        setAuthenticated(true);
      } catch {
        setAuthenticated(false);
      }
    }
    setLoading(false);
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: brand.backgroundColor }}>
        <Text style={{ color: brand.textColor, fontSize: 18 }}>{brand.appName}</Text>
      </View>
    );
  }

  if (!authenticated) {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <LoginScreen onLogin={() => setAuthenticated(true)} />
      </>
    );
  }

  return (
    <>
      <StatusBar barStyle="light-content" />
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={({ route }) => ({
            tabBarIcon: () => <TabIcon name={route.name} />,
            tabBarActiveTintColor: brand.primaryColor,
            tabBarInactiveTintColor: brand.textSecondary,
            tabBarStyle: {
              backgroundColor: brand.surfaceColor,
              borderTopColor: brand.surfaceColor,
            },
            headerShown: false,
          })}
        >
          <Tab.Screen name="Dashboard" component={DashboardScreen} />
          <Tab.Screen name="Cameras" component={CamerasScreen} />
          <Tab.Screen name="Alerts" component={AlertsScreen} />
          <Tab.Screen name="Search" component={SearchScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </>
  );
}
