import { useEffect, useState } from "react";
import type { AppProps } from "next/app";
import { useRouter } from "next/router";
import { Box, ChakraProvider } from "@chakra-ui/react";
import { AnimatePresence, motion } from "framer-motion";
import { PageTransitionOverlay } from "@/components/PageTransitionOverlay";
import { ThemeModeProvider, useThemeMode } from "@/components/theme-mode";
import { theme } from "@/theme";

function AppShell({ Component, pageProps }: AppProps) {
  const router = useRouter();
  const [isTransitioning, setIsTransitioning] = useState(false);
  const { palette } = useThemeMode();

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    function handleRouteStart() {
      setIsTransitioning(true);
    }

    function handleRouteDone() {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      timeoutId = setTimeout(() => {
        setIsTransitioning(false);
      }, 1520);
    }

    router.events.on("routeChangeStart", handleRouteStart);
    router.events.on("routeChangeComplete", handleRouteDone);
    router.events.on("routeChangeError", handleRouteDone);

    return () => {
      router.events.off("routeChangeStart", handleRouteStart);
      router.events.off("routeChangeComplete", handleRouteDone);
      router.events.off("routeChangeError", handleRouteDone);
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [router.events]);

  return (
    <Box minH="100vh" bg={palette.pageBg} color={palette.pageText} backgroundImage={palette.pageBgImage}>
      <PageTransitionOverlay active={isTransitioning} />
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={router.asPath}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -18 }}
          transition={{ duration: 0.92, ease: [0.22, 1, 0.36, 1] }}
        >
          <Component {...pageProps} />
        </motion.div>
      </AnimatePresence>
    </Box>
  );
}

export default function App(props: AppProps) {
  return (
    <ChakraProvider theme={theme}>
      <ThemeModeProvider>
        <AppShell {...props} />
      </ThemeModeProvider>
    </ChakraProvider>
  );
}
