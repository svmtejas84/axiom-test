import { Box, Text } from "@chakra-ui/react";
import { AnimatePresence, motion } from "framer-motion";
import { useThemeMode } from "@/components/theme-mode";

type PageTransitionOverlayProps = {
  active: boolean;
};

const MotionBox = motion(Box);

export function PageTransitionOverlay({ active }: PageTransitionOverlayProps) {
  const { palette, mode } = useThemeMode();

  return (
    <AnimatePresence>
      {active && (
        <MotionBox
          key="page-transition-overlay"
          position="fixed"
          inset="0"
          zIndex={2000}
          pointerEvents="none"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
        >
          <MotionBox
            position="absolute"
            inset="0"
            bg={palette.transitionOverlay}
            initial={{ clipPath: "inset(0 100% 0 0 round 0px)" }}
            animate={{ clipPath: "inset(0 0% 0 0 round 0px)" }}
            exit={{ clipPath: "inset(0 0 0 100% round 0px)" }}
            transition={{ duration: 2.25, ease: [0.22, 1, 0.36, 1] }}
          />

          <MotionBox
            position="absolute"
            top="50%"
            left="-560px"
            w={["420px", "560px", "680px"]}
            h={["250px", "320px", "380px"]}
            transform="translateY(-50%)"
            initial={{ x: 0, rotate: -4, scale: 0.98 }}
            animate={{ x: "calc(100vw + 720px)", rotate: 1, scale: 1.02 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 2.25, ease: [0.22, 1, 0.36, 1] }}
            filter={mode === "dark"
              ? "drop-shadow(0 28px 44px rgba(0, 0, 0, 0.38))"
              : "drop-shadow(0 28px 44px rgba(104, 3, 14, 0.18))"}
            borderRadius="34px"
            bg={palette.transitionCard}
            border={`1px solid ${palette.transitionCardBorder}`}
            overflow="hidden"
          >
            <MotionBox
              position="absolute"
              inset="0"
              bg="linear-gradient(115deg, rgba(255,255,255,0.32) 0%, rgba(255,255,255,0.06) 30%, rgba(255,255,255,0) 50%)"
              animate={{ x: ["-12%", "20%"] }}
              transition={{ duration: 1.9, repeat: Infinity, ease: "easeInOut" }}
            />
            <Box position="absolute" top="26px" left="30px" color={mode === "dark" ? "rgba(63,43,5,0.88)" : "rgba(255,248,233,0.92)"}>
              <Text fontSize="sm" fontWeight="bold" letterSpacing="0.12em">
                VOUCH
              </Text>
            </Box>
            <Box
              position="absolute"
              top="70px"
              left="30px"
              w="82px"
              h="58px"
              borderRadius="12px"
              bg={mode === "dark"
                ? "linear-gradient(135deg, rgba(255,241,168,0.95) 0%, rgba(208,156,39,0.95) 100%)"
                : "linear-gradient(135deg, rgba(255,244,214,0.95) 0%, rgba(242,158,8,0.95) 100%)"}
              boxShadow="inset 0 0 0 1px rgba(101,74,15,0.24)"
            />
            <Box
              position="absolute"
              right="34px"
              top="46px"
              w="240px"
              h="170px"
              borderRadius="999px"
              bg="radial-gradient(circle, rgba(255,255,255,0.22) 0%, rgba(255,255,255,0) 72%)"
            />
            <Box
              position="absolute"
              left="30px"
              right="30px"
              bottom="46px"
              h="2px"
              bg="linear-gradient(90deg, rgba(255,244,214,0.18) 0%, rgba(255,244,214,0.7) 50%, rgba(255,244,214,0.18) 100%)"
            />
          </MotionBox>

          <MotionBox
            position="absolute"
            top="50%"
            left="-220px"
            w="360px"
            h="12px"
            borderRadius="full"
              bg={mode === "dark"
                ? "linear-gradient(90deg, rgba(246,196,90,0) 0%, rgba(246,196,90,0.95) 50%, rgba(246,196,90,0) 100%)"
                : "linear-gradient(90deg, rgba(242,158,8,0) 0%, rgba(242,158,8,0.95) 45%, rgba(152,0,2,0.45) 70%, rgba(242,158,8,0) 100%)"}
            initial={{ x: 0, opacity: 0 }}
            animate={{ x: "calc(100vw + 420px)", opacity: [0, 1, 0] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 2.2, ease: [0.22, 1, 0.36, 1] }}
          />

          <MotionBox
            position="absolute"
            bottom="48px"
            left="50%"
            transform="translateX(-50%)"
            textAlign="center"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.55, delay: 0.22 }}
          >
            <Text color={palette.transitionLabel} letterSpacing="0.22em" fontSize="xs" fontWeight="bold">
              SWIPING INTO NEXT VIEW
            </Text>
          </MotionBox>
        </MotionBox>
      )}
    </AnimatePresence>
  );
}
