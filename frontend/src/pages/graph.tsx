import { Box, Container, Text, VStack } from "@chakra-ui/react";
import { InteractiveCard } from "@/components/InteractiveCard";
import { TopNav } from "@/components/TopNav";
import { useThemeMode } from "@/components/theme-mode";

const nodes = [
  { label: "Bank", top: "28%", left: "14%", accent: "#7cd67b" },
  { label: "Merchant", top: "14%", left: "50%", accent: "#f6c45a" },
  { label: "Landlord", top: "30%", left: "84%", accent: "#7cd67b" },
  { label: "Employer", top: "77%", left: "50%", accent: "#f6c45a" },
  { label: "Utility", top: "62%", left: "18%", accent: "#9bbcff" },
  { label: "Lender", top: "64%", left: "82%", accent: "#ff9f6a" },
];

export default function GraphPage() {
  const { palette, mode } = useThemeMode();
  const isDark = mode === "dark";
  const linkStroke = isDark ? "rgba(255,255,255,0.14)" : "rgba(104,3,14,0.14)";

  return (
    <Container maxW="container.xl" py={[5, 8]} px={[4, 6]}>
      <TopNav />
      <VStack spacing={8} align="stretch">
        <Box>
          <Text color={palette.accent} letterSpacing="0.18em" fontSize="xs" mb={2}>
            05. TRUST GRAPH
          </Text>
          <Text fontSize={["3xl", "4xl"]} fontWeight="bold">
            Full Network View
          </Text>
          <Text mt={3} color={palette.mutedText} maxW="780px">
            This full page expands the trust graph panel from the dashboard into a larger network view.
          </Text>
        </Box>

        <InteractiveCard tilt={5} scale={1.01}>
          <Box
            position="relative"
            h={["480px", "620px"]}
            borderWidth="1px"
            borderRadius="30px"
            bg={palette.cardBg}
            boxShadow={palette.cardShadow}
            overflow="hidden"
          >
          <svg width="100%" height="100%" viewBox="0 0 1200 700" preserveAspectRatio="none">
            <line x1="600" y1="350" x2="180" y2="210" stroke="#83d77c" strokeWidth="3" />
            <line x1="600" y1="350" x2="600" y2="120" stroke="#f6c45a" strokeWidth="3" />
            <line x1="600" y1="350" x2="1010" y2="230" stroke="#83d77c" strokeWidth="3" />
            <line x1="600" y1="350" x2="600" y2="560" stroke="#f6c45a" strokeWidth="3" />
            <line x1="600" y1="350" x2="230" y2="470" stroke="#9bbcff" strokeWidth="2" />
            <line x1="600" y1="350" x2="980" y2="470" stroke="#ff9f6a" strokeWidth="2" />
            <line x1="180" y1="210" x2="1010" y2="230" stroke={linkStroke} strokeWidth="1.5" />
            <line x1="180" y1="210" x2="600" y2="560" stroke={linkStroke} strokeWidth="1.5" />
            <line x1="1010" y1="230" x2="600" y2="560" stroke={linkStroke} strokeWidth="1.5" />
            <line x1="230" y1="470" x2="980" y2="470" stroke={linkStroke} strokeWidth="1.5" />
          </svg>

          {nodes.map((node) => (
            <Box
              key={node.label}
              position="absolute"
              top={node.top}
              left={node.left}
              transform="translate(-50%, -50%)"
              w={["92px", "112px"]}
              h={["92px", "112px"]}
              borderRadius="full"
              borderWidth="1px"
              bg={palette.subCardBg}
              display="flex"
              alignItems="center"
              justifyContent="center"
              flexDirection="column"
              textAlign="center"
              boxShadow={isDark ? "0 18px 40px rgba(0, 0, 0, 0.24)" : "0 18px 40px rgba(104, 3, 14, 0.08)"}
            >
              <Box w="14px" h="14px" borderRadius="full" bg={node.accent} mb={2} />
              <Text fontSize={["sm", "md"]}>{node.label}</Text>
            </Box>
          ))}

          <Box
            position="absolute"
            top="50%"
            left="50%"
            transform="translate(-50%, -50%)"
            w={["128px", "164px"]}
            h={["128px", "164px"]}
            borderRadius="full"
            border={`2px solid ${palette.accent}`}
            bg={isDark ? "rgba(246,196,90,0.08)" : "rgba(242,158,8,0.08)"}
            display="flex"
            alignItems="center"
            justifyContent="center"
            flexDirection="column"
            boxShadow={isDark ? "0 24px 80px rgba(246, 196, 90, 0.1)" : "0 24px 80px rgba(242, 158, 8, 0.12)"}
          >
            <Text fontSize={["4xl", "5xl"]}>•</Text>
            <Text fontWeight="bold" fontSize={["lg", "xl"]}>
              You
            </Text>
          </Box>
          </Box>
        </InteractiveCard>
      </VStack>
    </Container>
  );
}
