import { useEffect, useMemo, useState } from "react";
import NextLink from "next/link";
import Spline from "@splinetool/react-spline";
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Container,
  Flex,
  Grid,
  GridItem,
  HStack,
  SimpleGrid,
  Text,
  VStack,
} from "@chakra-ui/react";
import { InteractiveCard } from "@/components/InteractiveCard";
import { ResultOverview } from "@/components/ResultOverview";
import { TopNav } from "@/components/TopNav";
import { useThemeMode } from "@/components/theme-mode";

export default function DashboardPage() {
  const { palette, mode } = useThemeMode();
  return (
    <Container maxW="container.xl" py={[5, 8]} px={[4, 6]}>
      <TopNav />
      <VStack spacing={8} align="stretch">
        <Box>
          <Text color={palette.accent} letterSpacing="0.18em" fontSize="xs" mb={2}>
            04. DASHBOARD
          </Text>
          <Text fontSize={["3xl", "4xl"]} fontWeight="bold">
            Axiom Result Experience
          </Text>
          <Text color={palette.mutedText} mt={3} maxW="760px">
            This dashboard uses the backend score response and presents it in the
            same visual flow as your reference image.
          </Text>
        </Box>
        <ResultOverview />

        <InteractiveCard tilt={4} scale={1.01}>
          <Box p={[6, 8]} borderWidth="1px" borderRadius="30px" bg={palette.cardBg} boxShadow={palette.cardShadow}>
            <Text color={palette.accent} fontSize="sm" letterSpacing="0.14em" mb={5}>
              3D SCENE
            </Text>
            <Box
              h={["360px", "420px", "520px"]}
              borderWidth="1px"
              borderRadius="24px"
              overflow="hidden"
              bg={mode === "dark" ? "#050505" : "#fff6ea"}
            >
              <Spline scene="https://prod.spline.design/CCxvWVM0B1wGqJzX/scene.splinecode" />
            </Box>
          </Box>
        </InteractiveCard>
      </VStack>
    </Container>
  );
}
