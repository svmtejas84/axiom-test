import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type ThemeMode = "light" | "dark";

type ThemePalette = {
  pageBg: string;
  pageBgImage: string;
  pageText: string;
  mutedText: string;
  border: string;
  navBg: string;
  navBorder: string;
  navShadow: string;
  navText: string;
  navAccent: string;
  cardBg: string;
  cardShadow: string;
  subCardBg: string;
  heroGlow: string;
  heroStageBg: string;
  inputBg: string;
  inputText: string;
  inputBorder: string;
  buttonBg: string;
  buttonHover: string;
  buttonText: string;
  accent: string;
  accentStrong: string;
  accentSoft: string;
  transitionOverlay: string;
  transitionLabel: string;
  transitionCard: string;
  transitionCardBorder: string;
};

type ThemeModeContextValue = {
  mode: ThemeMode;
  palette: ThemePalette;
  toggleMode: () => void;
};

const THEME_MODE_STORAGE_KEY = "vouch_theme_mode";

const lightPalette: ThemePalette = {
  pageBg: "#f5efe6",
  pageBgImage:
    "radial-gradient(circle at top right, rgba(242, 158, 8, 0.22), transparent 26%), radial-gradient(circle at bottom left, rgba(152, 0, 2, 0.10), transparent 28%), linear-gradient(180deg, #faf6ee 0%, #f4ede3 100%)",
  pageText: "#231911",
  mutedText: "#6f5242",
  border: "rgba(152, 0, 2, 0.12)",
  navBg: "rgba(255, 250, 241, 0.94)",
  navBorder: "rgba(152, 0, 2, 0.14)",
  navShadow: "0 18px 40px rgba(104, 3, 14, 0.08)",
  navText: "#5d4032",
  navAccent: "#980002",
  cardBg: "rgba(255,250,241,0.98)",
  cardShadow: "0 18px 34px rgba(104, 3, 14, 0.05)",
  subCardBg: "rgba(255,255,255,0.62)",
  heroGlow: "radial-gradient(circle, rgba(242,158,8,0.22) 0%, rgba(226,89,5,0.08) 48%, rgba(0,0,0,0) 74%)",
  heroStageBg: "linear-gradient(180deg, rgba(255,244,214,0.95) 0%, rgba(255,239,210,0.95) 100%)",
  inputBg: "rgba(255,255,255,0.72)",
  inputText: "#231911",
  inputBorder: "rgba(152, 0, 2, 0.16)",
  buttonBg: "#F29E08",
  buttonHover: "#EC8805",
  buttonText: "#2a1608",
  accent: "#F29E08",
  accentStrong: "#980002",
  accentSoft: "#E25905",
  transitionOverlay: "linear-gradient(180deg, rgba(245,239,230,0.92) 0%, rgba(242,231,218,0.96) 100%)",
  transitionLabel: "#980002",
  transitionCard: "linear-gradient(135deg, #F29E08 0%, #EC8805 24%, #E25905 58%, #980002 100%)",
  transitionCardBorder: "rgba(255, 244, 214, 0.9)",
};

const darkPalette: ThemePalette = {
  pageBg: "#07090d",
  pageBgImage:
    "radial-gradient(circle at top, rgba(244, 190, 75, 0.16), transparent 32%), linear-gradient(180deg, #0a0d12 0%, #07090d 100%)",
  pageText: "#f6ead1",
  mutedText: "#b7ab8b",
  border: "rgba(245, 195, 86, 0.22)",
  navBg: "rgba(12, 15, 20, 0.9)",
  navBorder: "rgba(245, 195, 86, 0.18)",
  navShadow: "0 20px 60px rgba(0, 0, 0, 0.35)",
  navText: "#dbc79d",
  navAccent: "#f6c45a",
  cardBg: "rgba(16, 18, 24, 0.94)",
  cardShadow: "0 24px 80px rgba(0, 0, 0, 0.35)",
  subCardBg: "rgba(255,255,255,0.02)",
  heroGlow: "radial-gradient(circle, rgba(246,196,90,0.24) 0%, rgba(246,196,90,0) 70%)",
  heroStageBg:
    "radial-gradient(circle at 62% 42%, rgba(255,186,64,0.08), transparent 24%), radial-gradient(circle at 38% 64%, rgba(255,224,149,0.06), transparent 28%), linear-gradient(180deg, rgba(8,8,8,0.82) 0%, rgba(1,1,1,0.96) 100%)",
  inputBg: "rgba(10, 12, 16, 0.95)",
  inputText: "#f8eed7",
  inputBorder: "rgba(246,196,90,0.22)",
  buttonBg: "#f6c45a",
  buttonHover: "#ffd67d",
  buttonText: "#17130b",
  accent: "#f6c45a",
  accentStrong: "#f6c45a",
  accentSoft: "#c7b894",
  transitionOverlay: "linear-gradient(180deg, rgba(7,7,9,0.92) 0%, rgba(13,15,19,0.96) 100%)",
  transitionLabel: "#f6c45a",
  transitionCard: "linear-gradient(135deg, #fff1a8 0%, #f6d96a 16%, #d8a73b 44%, #f6c45a 66%, #fff0a2 100%)",
  transitionCardBorder: "rgba(255, 245, 190, 0.9)",
};

const ThemeModeContext = createContext<ThemeModeContextValue | null>(null);

export function ThemeModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>("light");

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const savedMode = window.localStorage.getItem(THEME_MODE_STORAGE_KEY);
    if (savedMode === "light" || savedMode === "dark") {
      setMode(savedMode);
    }
  }, []);

  const palette = mode === "dark" ? darkPalette : lightPalette;

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    document.body.style.backgroundColor = palette.pageBg;
    document.body.style.backgroundImage = palette.pageBgImage;
    document.body.style.color = palette.pageText;
  }, [palette]);

  const value = useMemo(
    () => ({
      mode,
      palette,
      toggleMode: () => {
        setMode((current) => {
          const next = current === "light" ? "dark" : "light";
          if (typeof window !== "undefined") {
            window.localStorage.setItem(THEME_MODE_STORAGE_KEY, next);
          }
          return next;
        });
      },
    }),
    [mode, palette]
  );

  return <ThemeModeContext.Provider value={value}>{children}</ThemeModeContext.Provider>;
}

export function useThemeMode() {
  const context = useContext(ThemeModeContext);

  if (!context) {
    throw new Error("useThemeMode must be used within ThemeModeProvider.");
  }

  return context;
}
