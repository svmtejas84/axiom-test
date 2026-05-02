import { Box, Container, Text, VStack } from "@chakra-ui/react";
import { ResultOverview } from "@/components/ResultOverview";
import { TopNav } from "@/components/TopNav";

export default function EvaluatePage() {
  return (
    <Container maxW="container.xl" py={[5, 8]} px={[4, 6]}>
      <TopNav />
      <VStack spacing={8} align="stretch">
        <Box>
          <Text
            fontSize={["3xl", "4xl"]}
            fontWeight="bold"
            maxW="800px"
          >
            Vouch Evaluation Result
          </Text>
        </Box>
        <ResultOverview />
      </VStack>
    </Container>
  );
}
