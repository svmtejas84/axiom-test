import { useState } from "react";
import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  Box,
  Button,
  FormControl,
  FormLabel,
  Grid,
  GridItem,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useForm } from "react-hook-form";
import { verifyRent, VerifyRequest, VerifyResponse } from "@/lib/api";
import { InteractiveCard } from "@/components/InteractiveCard";
import { useThemeMode } from "@/components/theme-mode";

type VerifyFormValues = {
  user_id: string;
  landlord_vpa: string;
  agreement_hash: string;
};

export function VerifyForm() {
  const { palette } = useThemeMode();
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<VerifyFormValues>({
    defaultValues: {
      user_id: "",
      landlord_vpa: "",
      agreement_hash: "",
    },
  });

  async function onSubmit(values: VerifyFormValues) {
    setError(null);
    setResult(null);

    const userId = values.user_id.trim();
    const landlordVpa = values.landlord_vpa.trim();
    const agreementHash = values.agreement_hash.trim();

    let hasValidationError = false;

    if (!userId) {
      setFieldError("user_id", {
        type: "required",
        message: "User ID is required",
      });
      hasValidationError = true;
    }

    if (!landlordVpa) {
      setFieldError("landlord_vpa", {
        type: "required",
        message: "Landlord VPA is required",
      });
      hasValidationError = true;
    }

    if (!agreementHash) {
      setFieldError("agreement_hash", {
        type: "required",
        message: "Agreement hash is required",
      });
      hasValidationError = true;
    }

    if (hasValidationError) {
      return;
    }

    const request: VerifyRequest = {
      user_id: userId,
      landlord_vpa: landlordVpa,
      agreement_hash: agreementHash,
    };

    try {
      const response = await verifyRent(request);
      setResult(response);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to verify rent.");
    }
  }

  return (
    <Grid templateColumns={["1fr", null, "1fr 0.9fr"]} gap={8}>
      <GridItem>
        <InteractiveCard tilt={4} scale={1.01}>
          <Box
            p={[6, 8]}
            borderWidth="1px"
            borderRadius="30px"
            bg={palette.cardBg}
            boxShadow={palette.cardShadow}
          >
          <VStack spacing={5} align="stretch">
            <Box>
              <Text color={palette.accent} letterSpacing="0.18em" fontSize="xs" mb={2}>
                BILATERAL VERIFICATION
              </Text>
              <Text fontSize="3xl" fontWeight="bold">
                Verify Rent Trust
              </Text>
              <Text mt={2} color={palette.mutedText}>
                Submit the landlord VPA and agreement hash to keep the same
                verification backend flow.
              </Text>
            </Box>

            <form onSubmit={handleSubmit(onSubmit)}>
              <VStack spacing={5} align="stretch">
                <FormControl isInvalid={!!errors.user_id}>
                  <FormLabel>User ID</FormLabel>
                  <Input
                    {...register("user_id")}
                    placeholder="user_123_abc"
                    h="56px"
                    borderRadius="18px"
                    bg={palette.inputBg}
                    color={palette.inputText}
                    borderColor={palette.inputBorder}
                    _placeholder={{ color: palette.mutedText }}
                  />
                  <Text color="#ff9075" mt={1} fontSize="sm">
                    {errors.user_id?.message}
                  </Text>
                </FormControl>

                <FormControl isInvalid={!!errors.landlord_vpa}>
                  <FormLabel>Landlord VPA</FormLabel>
                  <Input
                    {...register("landlord_vpa")}
                    placeholder="landlord@bankupi"
                    h="56px"
                    borderRadius="18px"
                    bg={palette.inputBg}
                    color={palette.inputText}
                    borderColor={palette.inputBorder}
                    _placeholder={{ color: palette.mutedText }}
                  />
                  <Text color="#ff9075" mt={1} fontSize="sm">
                    {errors.landlord_vpa?.message}
                  </Text>
                </FormControl>

                <FormControl isInvalid={!!errors.agreement_hash}>
                  <FormLabel>Agreement Hash</FormLabel>
                  <Input
                    {...register("agreement_hash")}
                    placeholder="sha256_hash"
                    h="56px"
                    borderRadius="18px"
                    bg={palette.inputBg}
                    color={palette.inputText}
                    borderColor={palette.inputBorder}
                    _placeholder={{ color: palette.mutedText }}
                  />
                  <Text color="#ff9075" mt={1} fontSize="sm">
                    {errors.agreement_hash?.message}
                  </Text>
                </FormControl>

                <Button
                  type="submit"
                  isLoading={isSubmitting}
                  h="58px"
                  borderRadius="18px"
                  bg={palette.buttonBg}
                  color={palette.buttonText}
                  _hover={{ bg: palette.buttonHover }}
                >
                  Verify Rent
                </Button>
              </VStack>
            </form>

            {error && (
              <Alert status="error" borderRadius="18px" bg="rgba(120, 24, 24, 0.35)">
                <AlertIcon />
                <Box>
                  <AlertTitle>Request failed</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Box>
              </Alert>
            )}
          </VStack>
          </Box>
        </InteractiveCard>
      </GridItem>

      <GridItem>
        <VStack spacing={6} align="stretch">
          <InteractiveCard tilt={4} scale={1.01}>
            <Box
              p={6}
              borderWidth="1px"
              borderRadius="24px"
              bg={palette.cardBg}
            >
            <Text color={palette.accent} fontWeight="semibold" mb={3}>
              Verification Output
            </Text>
            {result ? (
              <VStack align="stretch" spacing={3}>
                <Text>Verified: {result.is_verified ? "Yes" : "No"}</Text>
                <Text>Months Consistent: {result.months_consistent}</Text>
                <Text>Trust Coefficient: {result.trust_coefficient.toFixed(2)}</Text>
                <Text>Timestamp: {new Date(result.verification_timestamp).toLocaleString()}</Text>
              </VStack>
            ) : (
              <Text color={palette.mutedText}>
                The verified status, consistency window, and trust coefficient
                will appear here after the API responds.
              </Text>
            )}
            </Box>
          </InteractiveCard>

          <InteractiveCard tilt={4} scale={1.01}>
            <Box
              p={6}
              borderWidth="1px"
              borderRadius="24px"
              bg={palette.cardBg}
            >
            <Text color={palette.accent} fontWeight="semibold" mb={3}>
              What Stays the Same
            </Text>
            <VStack align="stretch" spacing={3} color={palette.mutedText}>
              <Text>Still calls `/v1/verify` with the same body fields.</Text>
              <Text>No backend scoring or verification logic was changed.</Text>
              <Text>Only the UI layer now matches the Axiom product look.</Text>
            </VStack>
            </Box>
          </InteractiveCard>
        </VStack>
      </GridItem>
    </Grid>
  );
}
