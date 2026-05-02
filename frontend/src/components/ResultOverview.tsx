import { useEffect, useMemo, useState } from "react";
import NextLink from "next/link";
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Flex,
  Grid,
  GridItem,
  HStack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { InteractiveCard } from "@/components/InteractiveCard";
import { getLatestScore, getScoreHistory, ScoreHistoryEntry } from "@/lib/storage";
import { useThemeMode } from "@/components/theme-mode";

type ResultOverviewProps = {
  showExplanation?: boolean;
};

function getTierColor(tier: string) {
  const normalizedTier = tier.toLowerCase();

  if (normalizedTier === "prime" || normalizedTier === "high") {
    return "#6fe08d";
  }
  if (normalizedTier === "medium") {
    return "#f2cf63";
  }
  return "#ff6b6b";
}

function getNeighborhoodDensity(score: number) {
  if (score >= 760) {
    return {
      label: "High Density",
      ringSize: "64px",
      ringTone: "radial-gradient(circle, rgba(111,224,141,0.72) 0%, rgba(61,170,96,0.28) 58%, rgba(0,0,0,0) 100%)",
      centerSize: "26px",
      centerTone: "#0f2416",
      withGrid: true,
      accentGlow: "radial-gradient(circle at center, rgba(111,224,141,0.46) 0%, rgba(246,196,90,0.24) 24%, rgba(58,232,160,0.24) 42%, rgba(22,91,53,0.14) 56%, rgba(0,0,0,0) 78%)",
      description: "Dense trusted activity cluster with strong local transaction confidence.",
    };
  }

  if (score >= 650) {
    return {
      label: "Medium Density",
      ringSize: "78px",
      ringTone: "radial-gradient(circle, rgba(242,207,99,0.72) 0%, rgba(184,115,18,0.28) 58%, rgba(0,0,0,0) 100%)",
      centerSize: "20px",
      centerTone: "#3a3011",
      withGrid: false,
      accentGlow: "radial-gradient(circle at center, rgba(242,207,99,0.38) 0%, rgba(255,171,64,0.24) 28%, rgba(246,196,90,0.18) 42%, rgba(122,76,16,0.14) 56%, rgba(0,0,0,0) 78%)",
      description: "Balanced local trust network with moderate signal concentration.",
    };
  }

  return {
    label: "Low Density",
      ringSize: "104px",
    ringTone: "radial-gradient(circle, rgba(255,107,107,0.62) 0%, rgba(172,39,39,0.22) 58%, rgba(0,0,0,0) 100%)",
    centerSize: "14px",
    centerTone: "#5a1f1f",
    withGrid: false,
    accentGlow: "radial-gradient(circle at center, rgba(255,107,107,0.36) 0%, rgba(255,141,64,0.18) 28%, rgba(255,107,107,0.14) 42%, rgba(122,20,20,0.14) 56%, rgba(0,0,0,0) 78%)",
    description: "Sparse trust network with lighter surrounding activity density.",
  };
}

export function ResultOverview({ showExplanation = true }: ResultOverviewProps) {
  const { palette, mode } = useThemeMode();
  const [latest, setLatest] = useState<ScoreHistoryEntry | null>(null);
  const [history, setHistory] = useState<ScoreHistoryEntry[]>([]);
  const isDark = mode === "dark";

  useEffect(() => {
    setLatest(getLatestScore());
    setHistory(getScoreHistory());
  }, []);

  const score = latest?.axiom_score ?? 742;
  const confidence = latest?.confidence_interval ?? 0.87;
  const tier = latest?.tier ?? "High";
  const verificationStatus = latest?.verification_status ?? "Bilateral Verified";
  const signalCount = latest?.signal_count ?? 12;
  const reasonCodes = latest?.behavioral_drivers ?? [];
  const tierColor = getTierColor(tier);
  const neighborhoodDensity = useMemo(() => getNeighborhoodDensity(score), [score]);

  const positiveFactors = useMemo(() => {
    const positives = reasonCodes
      .filter((item) => item.direction === "positive")
      .map((item) => item.driver);

    return positives.length
      ? positives
      : [
          "Stable income pattern",
          "On-time payment consistency",
          "Low volatility in essential spends",
          "Strong repayment reliability",
        ];
  }, [reasonCodes]);

  const negativeFactors = useMemo(() => {
    const negatives = reasonCodes
      .filter((item) => item.direction === "negative")
      .map((item) => item.driver);

    return negatives.length
      ? negatives
      : [
          "Short behavioral history",
          "Moderate savings variability",
          "Some cash-heavy periods",
          "Thin formal credit depth",
        ];
  }, [reasonCodes]);

  return (
    <VStack spacing={8} align="stretch">
      {!history.length && (
        <Alert borderRadius="18px" bg={isDark ? "rgba(245, 195, 86, 0.16)" : "rgba(242, 158, 8, 0.16)"} color={palette.pageText}>
          <AlertIcon />
          No live score found yet. Run an evaluation from the landing page to populate this result view.
        </Alert>
      )}

      <InteractiveCard tilt={5} scale={1.01}>
        <Box
          p={[7, 9]}
          borderWidth="1px"
          borderRadius="34px"
          bg={palette.cardBg}
          boxShadow={palette.cardShadow}
        >
        <Text color={palette.accent} fontSize="sm" letterSpacing="0.18em" mb={6}>
          VOUCH TRUST SCORE
        </Text>
        <VStack spacing={6} align="center">
          <Text color={palette.mutedText} fontSize="sm" letterSpacing="0.16em" textAlign="center">
            LIVE TRUST OUTCOME
          </Text>
          <Flex justify="center" w="100%">
            <Box
              w={["280px", "360px", "430px"]}
              h={["280px", "360px", "430px"]}
              borderRadius="full"
              border={isDark ? "22px solid rgba(255,255,255,0.08)" : "22px solid rgba(104,3,14,0.08)"}
              borderTopColor={tierColor}
              borderRightColor={tierColor}
              boxShadow={isDark ? "0 0 0 14px rgba(255,255,255,0.03)" : "0 0 0 14px rgba(242,158,8,0.08)"}
              position="relative"
              bg={palette.subCardBg}
            >
              <Flex position="absolute" inset="0" align="center" justify="center" direction="column">
                <Text fontSize={["6xl", "8xl", "9xl"]} fontWeight="900" lineHeight="0.95">
                  {score}
                </Text>
                <Text color={tierColor} fontWeight="bold" letterSpacing="0.16em" fontSize={["md", "lg"]}>
                  {tier.toUpperCase()}
                </Text>
              </Flex>
            </Box>
          </Flex>
          <Text color={palette.mutedText} maxW="520px" textAlign="center">
            Vouch translates behavioral finance signals into a trust score that is easy to understand and ready to act on.
          </Text>
        </VStack>
        </Box>
      </InteractiveCard>

      <Grid templateColumns={["1fr", null, "1.1fr 0.9fr"]} gap={8}>
        <GridItem>
          <InteractiveCard tilt={4} scale={1.01}>
            <Box p={[6, 8]} borderWidth="1px" borderRadius="30px" bg={palette.cardBg} boxShadow={palette.cardShadow}>
            <Text color={palette.accent} fontSize="sm" letterSpacing="0.14em" mb={5}>
              RESULT DETAILS
            </Text>
            <VStack spacing={4} align="stretch">
              <Box p={5} borderWidth="1px" borderRadius="22px" bg={palette.subCardBg}>
                <Text color={palette.mutedText} fontSize="sm">
                  Vouch Score
                </Text>
                <Text mt={2} fontSize="3xl" fontWeight="bold">
                  {score}
                </Text>
              </Box>
              <Box p={5} borderWidth="1px" borderRadius="22px" bg={palette.subCardBg}>
                <Text color={palette.mutedText} fontSize="sm">
                  Credit Tier
                </Text>
                <Text mt={2} fontSize="3xl" fontWeight="bold" color={tierColor}>
                  {tier}
                </Text>
              </Box>
              <Box p={5} borderWidth="1px" borderRadius="22px" bg={palette.subCardBg}>
                <Text color={palette.mutedText} fontSize="sm">
                  Confidence Score
                </Text>
                <Text mt={2} fontSize="3xl" fontWeight="bold">
                  {confidence.toFixed(2)}
                </Text>
              </Box>
              <Box p={5} borderWidth="1px" borderRadius="22px" bg={palette.subCardBg}>
                <Text color={palette.mutedText} fontSize="sm">
                  Verification
                </Text>
                <Text mt={2} fontSize="xl" fontWeight="bold">
                  {verificationStatus}
                </Text>
              </Box>
            </VStack>
            </Box>
          </InteractiveCard>
        </GridItem>

        <GridItem>
          <VStack spacing={4} align="stretch">
            <InteractiveCard tilt={4} scale={1.01}>
              <Box p={5} borderWidth="1px" borderRadius="24px" bg={palette.cardBg}>
              <Text color={palette.mutedText} fontSize="sm">
                Signal Count
              </Text>
              <Text mt={2} fontSize="2xl" fontWeight="bold">
                {signalCount}
              </Text>
              </Box>
            </InteractiveCard>
            <InteractiveCard tilt={4} scale={1.01}>
              <Box p={5} borderWidth="1px" borderRadius="24px" bg={palette.cardBg}>
              <Text color={palette.mutedText} fontSize="sm" mb={4}>
                Neighborhood Density
              </Text>
              <Box
                position="relative"
                h="210px"
                borderWidth="1px"
                borderRadius="24px"
                overflow="hidden"
                bg={neighborhoodDensity.withGrid
                  ? `linear-gradient(rgba(246,196,90,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(246,196,90,0.07) 1px, transparent 1px), ${palette.subCardBg}`
                  : palette.subCardBg}
                backgroundSize={neighborhoodDensity.withGrid ? "24px 24px, 24px 24px, auto" : "auto"}
              >
                <Box position="absolute" inset="0" bg={neighborhoodDensity.accentGlow} />
                <Box position="absolute" inset="0" bg="radial-gradient(circle at 20% 18%, rgba(246,196,90,0.16) 0%, rgba(0,0,0,0) 20%), radial-gradient(circle at 82% 24%, rgba(104,220,176,0.14) 0%, rgba(0,0,0,0) 18%), radial-gradient(circle at 18% 82%, rgba(255,125,107,0.12) 0%, rgba(0,0,0,0) 16%), radial-gradient(circle at 84% 78%, rgba(133,177,255,0.12) 0%, rgba(0,0,0,0) 18%)" />
                <Box position="absolute" top="26px" left="28px" w="12px" h="12px" borderRadius="full" bg={tierColor} boxShadow={`0 0 18px ${tierColor}`} />
                <Box position="absolute" top="52px" right="42px" w="10px" h="10px" borderRadius="full" bg="#f6c45a" boxShadow="0 0 16px rgba(246,196,90,0.75)" />
                <Box position="absolute" bottom="30px" left="36px" w="14px" h="14px" borderRadius="full" bg="#79b8ff" boxShadow="0 0 16px rgba(121,184,255,0.56)" />
                <Box position="absolute" bottom="46px" right="34px" w="16px" h="16px" borderRadius="full" bg={tierColor} boxShadow={`0 0 20px ${tierColor}`} />
                <Box position="absolute" top="84px" left="78px" w="72px" h="1px" bg="linear-gradient(90deg, rgba(246,196,90,0.04) 0%, rgba(246,196,90,0.32) 50%, rgba(246,196,90,0.04) 100%)" transform="rotate(-18deg)" />
                <Box position="absolute" top="78px" right="72px" w="82px" h="1px" bg={`linear-gradient(90deg, rgba(255,255,255,0.02) 0%, ${tierColor}66 50%, rgba(255,255,255,0.02) 100%)`} transform="rotate(22deg)" />
                <Box position="absolute" bottom="70px" left="72px" w="88px" h="1px" bg="linear-gradient(90deg, rgba(121,184,255,0.04) 0%, rgba(121,184,255,0.34) 50%, rgba(121,184,255,0.04) 100%)" transform="rotate(14deg)" />
                <Box position="absolute" bottom="82px" right="64px" w="74px" h="1px" bg="linear-gradient(90deg, rgba(255,125,107,0.04) 0%, rgba(255,125,107,0.32) 50%, rgba(255,125,107,0.04) 100%)" transform="rotate(-16deg)" />
                <Flex position="absolute" inset="0" align="center" justify="center">
                  <Box
                    w={neighborhoodDensity.ringSize}
                    h={neighborhoodDensity.ringSize}
                    borderRadius="full"
                    bg={neighborhoodDensity.ringTone}
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                    boxShadow={neighborhoodDensity.withGrid ? `0 0 0 14px rgba(246,196,90,0.10), 0 0 36px ${tierColor}, 0 0 84px rgba(246,196,90,0.18)` : `0 0 24px ${tierColor}, 0 0 56px rgba(246,196,90,0.12)`}
                  >
                    <Box
                      w={neighborhoodDensity.centerSize}
                      h={neighborhoodDensity.centerSize}
                      borderRadius="full"
                      bg={neighborhoodDensity.centerTone}
                    />
                  </Box>
                </Flex>
              </Box>
              <Text mt={4} fontWeight="bold">
                {neighborhoodDensity.label}
              </Text>
              <Text mt={1} color={palette.mutedText} fontSize="sm">
                {neighborhoodDensity.description}
              </Text>
              </Box>
            </InteractiveCard>
          </VStack>
        </GridItem>
      </Grid>

      {showExplanation && (
        <InteractiveCard tilt={4} scale={1.01}>
          <Box p={[6, 8]} borderWidth="1px" borderRadius="30px" bg={palette.cardBg} boxShadow={palette.cardShadow}>
          <Text color={palette.accent} fontSize="sm" letterSpacing="0.14em" mb={5}>
            EXPLANATION
          </Text>
          <Grid templateColumns={["1fr", null, "1fr 1fr"]} gap={6}>
            <GridItem>
              <Box p={5} borderWidth="1px" borderRadius="22px" h="100%">
                <Text fontSize="xl" fontWeight="bold" mb={4}>
                  Positive Factors
                </Text>
                <VStack align="stretch" spacing={3}>
                  {positiveFactors.map((factor) => (
                    <HStack key={factor} align="flex-start">
                      <Box mt={1} w="10px" h="10px" borderRadius="full" bg="#7cd67b" />
                      <Text>{factor}</Text>
                    </HStack>
                  ))}
                </VStack>
              </Box>
            </GridItem>
            <GridItem>
              <Box p={5} borderWidth="1px" borderRadius="22px" h="100%">
                <Text fontSize="xl" fontWeight="bold" mb={4}>
                  Negative Factors
                </Text>
                <VStack align="stretch" spacing={3}>
                  {negativeFactors.map((factor) => (
                    <HStack key={factor} align="flex-start">
                      <Box mt={1} w="10px" h="10px" borderRadius="full" bg="#ff7b6b" />
                      <Text>{factor}</Text>
                    </HStack>
                  ))}
                </VStack>
              </Box>
            </GridItem>
          </Grid>
          </Box>
        </InteractiveCard>
      )}

      <Flex justify="center">
        <Button
          as={NextLink}
          href="/more-info"
          h="56px"
          px={10}
          borderRadius="18px"
          bg={palette.buttonBg}
          color={palette.buttonText}
          fontWeight="bold"
          _hover={{ bg: palette.buttonHover }}
        >
          More Info
        </Button>
      </Flex>
    </VStack>
  );
}
