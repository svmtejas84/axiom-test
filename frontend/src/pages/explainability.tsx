import { Box, Container, Grid, GridItem, HStack, Text, VStack } from "@chakra-ui/react";
import { InteractiveCard } from "@/components/InteractiveCard";
import { TopNav } from "@/components/TopNav";
import { useThemeMode } from "@/components/theme-mode";

const positiveFactors = [
  "Stable income pattern",
  "On-time payment consistency",
  "Low volatility in essential spends",
  "Strong merchant trust network",
  "Verified rent behavior",
];

const negativeFactors = [
  "Short behavioral history",
  "Moderate savings variability",
  "Some cash-heavy periods",
  "Thin formal credit depth",
  "Irregular spending spikes",
];

export default function ExplainabilityPage() {
  const { palette } = useThemeMode();
  return (
    <Container maxW="container.xl" py={[5, 8]} px={[4, 6]}>
      <TopNav />
      <VStack spacing={8} align="stretch">
        <Box>
          <Text color={palette.accent} letterSpacing="0.18em" fontSize="xs" mb={2}>
            06. EXPLAINABILITY
          </Text>
          <Text fontSize={["3xl", "4xl"]} fontWeight="bold">
            Why This Score?
          </Text>
          <Text mt={3} color={palette.mutedText} maxW="780px">
            This page expands the explainability section so users can review the strongest positive and negative trust factors.
          </Text>
        </Box>

        <Grid templateColumns={["1fr", null, "1fr 1fr"]} gap={8}>
          <GridItem>
            <InteractiveCard tilt={4} scale={1.01}>
              <Box p={[6, 8]} borderWidth="1px" borderRadius="30px" bg={palette.cardBg} boxShadow={palette.cardShadow}>
              <Text fontSize="2xl" fontWeight="bold" mb={5}>
                Positive Factors
              </Text>
              <VStack align="stretch" spacing={4}>
                {positiveFactors.map((factor) => (
                  <HStack key={factor} align="flex-start" p={4} borderWidth="1px" borderRadius="18px">
                    <Box mt={1} w="10px" h="10px" borderRadius="full" bg="#7cd67b" />
                    <Text>{factor}</Text>
                  </HStack>
                ))}
              </VStack>
              </Box>
            </InteractiveCard>
          </GridItem>

          <GridItem>
            <InteractiveCard tilt={4} scale={1.01}>
              <Box p={[6, 8]} borderWidth="1px" borderRadius="30px" bg={palette.cardBg} boxShadow={palette.cardShadow}>
              <Text fontSize="2xl" fontWeight="bold" mb={5}>
                Negative Factors
              </Text>
              <VStack align="stretch" spacing={4}>
                {negativeFactors.map((factor) => (
                  <HStack key={factor} align="flex-start" p={4} borderWidth="1px" borderRadius="18px">
                    <Box mt={1} w="10px" h="10px" borderRadius="full" bg="#ff7b6b" />
                    <Text>{factor}</Text>
                  </HStack>
                ))}
              </VStack>
              </Box>
            </InteractiveCard>
          </GridItem>
        </Grid>
      </VStack>
    </Container>
  );
}
