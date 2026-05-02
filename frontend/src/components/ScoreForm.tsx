import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  Box,
  Button,
  Flex,
  FormControl,
  FormLabel,
  Grid,
  GridItem,
  HStack,
  Input,
  Progress,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useForm } from "react-hook-form";
import { scoreUser, ScoreRequest, ScoreResponse, verifyStudent } from "@/lib/api";
import { saveScoreHistory, ScoreHistoryEntry, ScoreInputMethod } from "@/lib/storage";
import { InteractiveCard } from "@/components/InteractiveCard";
import { useThemeMode } from "@/components/theme-mode";

type ScoreFormValues = {
  user_id: string;
  consent_handle?: string;
  upi_id?: string;
  phone_number?: string;
  parent_vpa?: string;
  student_mail_verification?: string;
  landlord_vpa?: string;
  include_reasons: boolean;
};

type ScoreFormProps = {
  title?: string;
  eyebrow?: string;
  description?: string;
  redirectTo?: string;
  showPipeline?: boolean;
  showUserIdField?: boolean;
};

const pipelineSteps = [
  "Collecting behavioral signals",
  "Building trust graph",
  "Running AI model",
  "Preparing score insights",
];

const methodCards: Array<{
  id: ScoreInputMethod | "documents";
  title: string;
  description: string;
}> = [
  {
    id: "upi_id",
    title: "UPI ID",
    description: "Score a user directly from a UPI handle.",
  },
  {
    id: "phone_number",
    title: "Phone No",
    description: "Fetch linked bank accounts from a phone number.",
  },
  {
    id: "documents",
    title: "Document Upload",
    description: "Attach bank, rent, or utility proofs for evaluation context.",
  },
];

const verificationCards = [
  {
    id: "student_verification",
    title: "Student Verification",
    description: "Attach education-linked proof signals for student trust evaluation.",
  },
  {
    id: "rent_verification",
    title: "Rent Verification",
    description: "Use rent and landlord-linked details as optional verification context.",
  },
] as const;

function formatRequest(values: ScoreFormValues, method: ScoreInputMethod): ScoreRequest {
  const request: ScoreRequest = {
    user_id: values.user_id,
    include_reasons: values.include_reasons,
    parent_vpa: values.parent_vpa,
    landlord_vpa: values.landlord_vpa,
    edu_email: values.student_mail_verification,
  };

  if (method === "consent_handle") {
    request.consent_handle = values.consent_handle;
  }
  if (method === "upi_id") {
    request.upi_id = values.upi_id;
  }
  if (method === "phone_number") {
    request.phone_number = values.phone_number;
  }

  return request;
}

function buildHistoryEntry(
  request: ScoreRequest,
  inputMethod: ScoreInputMethod,
  response: ScoreResponse
): ScoreHistoryEntry {
  return {
    ...response,
    user_id: request.user_id,
    input_method: inputMethod,
    requested_at: new Date().toISOString(),
  };
}

export function ScoreForm({
  title = "Choose Your Input Method",
  eyebrow = "02. INPUT METHODS",
  description = "Pick how you want to identify the user, then submit for scoring.",
  redirectTo = "/evaluate",
  showPipeline = true,
  showUserIdField = true,
}: ScoreFormProps) {
  const router = useRouter();
  const { palette, mode } = useThemeMode();
  const [selectedMethod, setSelectedMethod] = useState<ScoreInputMethod | null>(null);
  const [selectedVerification, setSelectedVerification] = useState<string | null>(null);
  const [rentVerificationMethod, setRentVerificationMethod] = useState<"landlord_vpa" | "documents" | null>(null);
  const [showDocuments, setShowDocuments] = useState(false);
  const [documents, setDocuments] = useState<File[]>([]);
  const [rentDocuments, setRentDocuments] = useState<File[]>([]);
  const [methodError, setMethodError] = useState<string | null>(null);
  const [isStudentVerified, setIsStudentVerified] = useState(false);
  const [isRentVerified, setIsRentVerified] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [result, setResult] = useState<ScoreResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pipelineStage, setPipelineStage] = useState(0);
  const [progress, setProgress] = useState(12);
  const isDark = mode === "dark";
  const selectedGradient = isDark
    ? "linear-gradient(180deg, #f6c45a 0%, #d8a73b 100%)"
    : `linear-gradient(180deg, ${palette.buttonBg} 0%, ${palette.accentSoft} 100%)`;
  const idleGradient = isDark
    ? "linear-gradient(180deg, rgba(34,37,46,0.96) 0%, rgba(18,20,27,0.98) 100%)"
    : "linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(247,240,230,0.98) 100%)";
  const idleBorder = isDark ? "rgba(246,196,90,0.2)" : palette.inputBorder;
  const idleCardText = isDark ? "#f6ead1" : palette.pageText;
  const idleMutedText = isDark ? "#a99972" : palette.mutedText;
  const activeMutedText = isDark ? "rgba(23,19,11,0.8)" : "rgba(42,22,8,0.84)";

  const {
    register,
    handleSubmit,
    setError: setFieldError,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<ScoreFormValues>({
    defaultValues: {
      user_id: "",
      consent_handle: "",
      upi_id: "",
      phone_number: "",
      parent_vpa: "",
      student_mail_verification: "",
      landlord_vpa: "",
      include_reasons: true,
    },
  });


  useEffect(() => {
    if (!isSubmitting) {
      setPipelineStage(0);
      setProgress(12);
      return;
    }

    const timer = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 92) {
          return current;
        }

        const next = Math.min(current + 14, 92);
        setPipelineStage(Math.min(Math.floor(next / 26), pipelineSteps.length - 1));
        return next;
      });
    }, 700);

    return () => window.clearInterval(timer);
  }, [isSubmitting]);

  useEffect(() => {
    if (showUserIdField || typeof window === "undefined") {
      return;
    }

    const savedUserId = window.localStorage.getItem("vouch_user_id");
    if (!savedUserId) {
      return;
    }

    setValue("user_id", savedUserId);
  }, [setValue, showUserIdField]);

  const activeInputLabel = useMemo(() => {
    if (selectedMethod === "consent_handle") {
      return "Consent Handle";
    }
    if (selectedMethod === "phone_number") {
      return "Phone Number";
    }
    if (selectedMethod === "upi_id") {
      return "UPI ID";
    }
    return "Selected Method";
  }, [selectedMethod]);

  function chooseMethod(method: ScoreInputMethod | "documents") {
    setMethodError(null);
    setSelectedVerification(null);
    setRentVerificationMethod(null);
    if (method === "documents") {
      setSelectedMethod(null);
      setShowDocuments(true);
      return;
    }
    setShowDocuments(false);
    setSelectedMethod(method);
  }

  function chooseVerification(verification: string) {
    setSelectedVerification((current) => (current === verification ? null : verification));
    if (verification !== "rent_verification") {
      setRentVerificationMethod(null);
    }
  }

  async function onVerifyStudent() {
    const values = getValues();
    const userId = values.user_id.trim();
    if (!userId || !values.student_mail_verification) {
      setError("Please enter User ID and Student Email first.");
      return;
    }

    setIsVerifying(true);
    setError(null);
    try {
      await verifyStudent({
        user_id: userId,
        first_name: "Axiom",
        last_name: "User",
        birth_date: "2000-01-01",
        edu_email: values.student_mail_verification,
        organization_id: 1,
        organization_name: "University",
        parents_vpa: values.parent_vpa || "parent@upi",
      });
      setIsStudentVerified(true);
    } catch (err: any) {
      setError(err.message);
      setIsStudentVerified(false);
    } finally {
      setIsVerifying(false);
    }
  }

  async function onVerifyRent() {
    const values = getValues();
    const userId = values.user_id.trim();
    if (!userId || !values.landlord_vpa) {
      setError("Please enter User ID and Landlord VPA first.");
      return;
    }

    setIsVerifying(true);
    setError(null);
    try {
      await verifyRent({
        user_id: userId,
        landlord_vpa: values.landlord_vpa,
        agreement_hash: "simulated_hash",
      });
      setIsRentVerified(true);
    } catch (err: any) {
      setError(err.message);
      setIsRentVerified(false);
    } finally {
      setIsVerifying(false);
    }
  }

  async function onSubmit(values: ScoreFormValues) {
    setError(null);
    setResult(null);
    setMethodError(null);

    const userId = values.user_id.trim();
    if (!userId) {
      setFieldError("user_id", {
        type: "required",
        message: "User ID is required",
      });
      return;
    }

    if (typeof window !== "undefined") {
      window.localStorage.setItem("vouch_user_id", userId);
    }

    if (!selectedMethod) {
      setMethodError("Choose UPI ID or Phone No before running evaluation.");
      return;
    }

    if (selectedMethod === "upi_id" && !values.upi_id?.trim()) {
      setFieldError("upi_id", {
        type: "required",
        message: "UPI ID is required",
      });
      return;
    }

    if (selectedMethod === "phone_number" && !values.phone_number?.trim()) {
      setFieldError("phone_number", {
        type: "required",
        message: "Phone number is required",
      });
      return;
    }

    const request = formatRequest(values, selectedMethod);
    request.user_id = userId;

    try {
      // 1. If student verification is active, call the verification endpoint first
      if (selectedVerification === "student_verification") {
        await verifyStudent({
          user_id: userId,
          first_name: "Mock", 
          last_name: "Student",
          birth_date: "2000-01-01",
          edu_email: values.student_mail_verification || "",
          organization_id: 1234,
          organization_name: "Axiom University",
          parents_vpa: values.parent_vpa || "",
        });
      }

      // 2. If rent verification is active, call the rent verification endpoint
      if (selectedVerification === "rent_verification" && rentVerificationMethod === "landlord_vpa") {
        await verifyRent({
          user_id: userId,
          landlord_vpa: values.landlord_vpa || "",
          agreement_hash: "simulated_agreement_hash",
        });
      }

      // 3. Call the main scoring endpoint
      const response = await scoreUser(request);
      setProgress(100);
      setPipelineStage(pipelineSteps.length - 1);
      setResult(response);
      saveScoreHistory(buildHistoryEntry(request, selectedMethod, response));

      window.setTimeout(() => {
        void router.push(redirectTo);
      }, 500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to fetch score. Please check your network connection and backend status.");
    }
  }

  function handleDocumentChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files ? Array.from(event.target.files) : [];
    setDocuments(files);
  }

  return (
    <Grid templateColumns={showPipeline ? ["1fr", null, "1.05fr 0.95fr"] : ["1fr"]} gap={8}>
      <GridItem>
        <InteractiveCard tilt={4} scale={1.01}>
          <Box
            p={[6, 8]}
            borderWidth="1px"
            borderRadius="30px"
            bg={palette.cardBg}
            boxShadow={palette.cardShadow}
          >
          <VStack align="stretch" spacing={6}>
            <Box>
              <Text color={palette.accent} letterSpacing="0.18em" fontSize="xs" mb={2}>
                {eyebrow}
              </Text>
              <Text fontSize={["3xl", "4xl"]} fontWeight="bold">
                {title}
              </Text>
              <Text color={palette.mutedText} mt={2}>
                {description}
              </Text>
            </Box>

            <Box>
              <Text color={palette.pageText} mb={3} fontWeight="semibold">
                Input Methods
              </Text>
              <Grid templateColumns={["1fr", null, "repeat(3, 1fr)"]} gap={4}>
                {methodCards.map((method) => {
                  const active =
                    method.id === selectedMethod || (method.id === "documents" && showDocuments);

                  return (
                    <VStack key={method.id} align="stretch" spacing={3}>
                      <Button
                        type="button"
                        onClick={() => chooseMethod(method.id)}
                        h={["64px", "72px"]}
                        px={6}
                        py={4}
                        justifyContent="center"
                        textAlign="center"
                        borderRadius="18px"
                        borderWidth="1px"
                        fontSize="md"
                        fontWeight="bold"
                        boxShadow={active ? "0 12px 28px rgba(246,196,90,0.18)" : "0 10px 24px rgba(0,0,0,0.22)"}
                        bg={active ? selectedGradient : idleGradient}
                        borderColor={active ? palette.accent : idleBorder}
                        color={active ? palette.buttonText : idleCardText}
                        _hover={{
                          transform: "translateY(-2px)",
                          boxShadow: "0 14px 30px rgba(246,196,90,0.24)",
                          borderColor: palette.accent,
                        }}
                        _active={{ transform: "translateY(0)" }}
                        transition="all 0.2s ease"
                      >
                        <VStack align="center" spacing={1}>
                          <Text color="inherit" fontWeight="bold">
                            {method.title}
                          </Text>
                          <Text
                            color={active ? activeMutedText : idleMutedText}
                            whiteSpace="normal"
                            fontSize="xs"
                            fontWeight="normal"
                            maxW="180px"
                          >
                            {method.description}
                          </Text>
                        </VStack>
                      </Button>

                      {method.id === "upi_id" && selectedMethod === "upi_id" && (
                        <FormControl isInvalid={!!errors.upi_id}>
                          <Input
                            {...register("upi_id")}
                            placeholder="user@bankupi"
                            h="52px"
                            borderRadius="16px"
                            bg={palette.inputBg}
                            color={palette.inputText}
                            borderColor={palette.inputBorder}
                            _placeholder={{ color: palette.mutedText }}
                          />
                          <Text color="#ff9075" mt={1} fontSize="sm">
                            {errors.upi_id?.message}
                          </Text>
                        </FormControl>
                      )}

                      {method.id === "phone_number" && selectedMethod === "phone_number" && (
                        <FormControl isInvalid={!!errors.phone_number}>
                          <Input
                            {...register("phone_number")}
                            placeholder="+91 9876543210"
                            h="52px"
                            borderRadius="16px"
                            bg={palette.inputBg}
                            color={palette.inputText}
                            borderColor={palette.inputBorder}
                            _placeholder={{ color: palette.mutedText }}
                          />
                          <Text color="#ff9075" mt={1} fontSize="sm">
                            {errors.phone_number?.message}
                          </Text>
                        </FormControl>
                      )}

                      {method.id === "documents" && showDocuments && (
                        <FormControl>
                          <Input
                            type="file"
                            multiple
                            accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                            onChange={handleDocumentChange}
                            h="auto"
                            py={3}
                            borderRadius="16px"
                            bg={palette.inputBg}
                            color={palette.inputText}
                            borderColor={palette.inputBorder}
                          />
                          <Text mt={2} color={palette.mutedText} fontSize="sm">
                            Add bank statements, utility bills, rent proofs, or other supporting files.
                          </Text>
                          {documents.length > 0 && (
                            <VStack mt={3} align="stretch" spacing={2}>
                              {documents.map((file) => (
                                <Text key={`${file.name}-${file.size}`} color={palette.pageText} fontSize="sm">
                                  {file.name}
                                </Text>
                              ))}
                            </VStack>
                          )}
                        </FormControl>
                      )}
                    </VStack>
                  );
                })}
              </Grid>
              {methodError && (
                <Text color="#ff9075" mt={3} fontSize="sm">
                  {methodError}
                </Text>
              )}
            </Box>

            <Box>
              <Text color={palette.pageText} mb={3} fontWeight="semibold">
                Optional Verification
              </Text>
              <Grid templateColumns={["1fr", null, "repeat(2, 1fr)"]} gap={4}>
                {verificationCards.map((verification) => {
                  const active = verification.id === selectedVerification;

                  return (
                    <VStack key={verification.id} align="stretch" spacing={3}>
                      <Button
                        type="button"
                        onClick={() => chooseVerification(verification.id)}
                        h={["64px", "72px"]}
                        px={6}
                        py={4}
                        justifyContent="center"
                        textAlign="center"
                        borderRadius="18px"
                        borderWidth="1px"
                        fontSize="md"
                        fontWeight="bold"
                        boxShadow={active ? "0 12px 28px rgba(246,196,90,0.18)" : "0 10px 24px rgba(0,0,0,0.22)"}
                        bg={active ? selectedGradient : idleGradient}
                        borderColor={active ? palette.accent : idleBorder}
                        color={active ? palette.buttonText : idleCardText}
                        _hover={{
                          transform: "translateY(-2px)",
                          boxShadow: "0 14px 30px rgba(246,196,90,0.24)",
                          borderColor: palette.accent,
                        }}
                        _active={{ transform: "translateY(0)" }}
                        transition="all 0.2s ease"
                      >
                        <VStack align="center" spacing={1}>
                          <Text color="inherit" fontWeight="bold">
                            {verification.title}
                          </Text>
                          <Text
                            color={active ? activeMutedText : idleMutedText}
                            whiteSpace="normal"
                            fontSize="xs"
                            fontWeight="normal"
                            maxW="220px"
                          >
                            {verification.description}
                          </Text>
                        </VStack>
                      </Button>

                      {verification.id === "student_verification" && selectedVerification === "student_verification" && (
                        <VStack align="stretch" spacing={3}>
                          <FormControl>
                            <Input
                              {...register("parent_vpa")}
                              placeholder="Parent VPA"
                              h="52px"
                              borderRadius="16px"
                              bg={palette.inputBg}
                              color={palette.inputText}
                              borderColor={palette.inputBorder}
                              _placeholder={{ color: palette.mutedText }}
                            />
                          </FormControl>
                          <FormControl>
                            <Input
                              {...register("student_mail_verification")}
                              placeholder="Student Mail Verification"
                              h="52px"
                              borderRadius="16px"
                              bg={palette.inputBg}
                              color={palette.inputText}
                              borderColor={palette.inputBorder}
                              _placeholder={{ color: palette.mutedText }}
                            />
                          </FormControl>
                          <Button
                            onClick={onVerifyStudent}
                            isLoading={isVerifying}
                            loadingText="Verifying"
                            isDisabled={isStudentVerified}
                            bg={isStudentVerified ? "green.500" : palette.buttonBg}
                            color="white"
                            size="md"
                            borderRadius="14px"
                            mt={2}
                          >
                            {isStudentVerified ? "✓ Verified" : "Verify Student"}
                          </Button>
                        </VStack>
                      )}

                      {verification.id === "rent_verification" && selectedVerification === "rent_verification" && (
                        <VStack align="stretch" spacing={3}>
                          <Grid templateColumns={["1fr", "1fr 1fr"]} gap={3}>
                            <Button
                              type="button"
                              h="48px"
                              borderRadius="16px"
                              borderWidth="1px"
                              bg={rentVerificationMethod === "landlord_vpa"
                                ? selectedGradient
                                : palette.subCardBg}
                              borderColor={rentVerificationMethod === "landlord_vpa" ? palette.accent : idleBorder}
                              color={rentVerificationMethod === "landlord_vpa" ? palette.buttonText : idleCardText}
                              onClick={() => setRentVerificationMethod("landlord_vpa")}
                              _hover={{ borderColor: palette.accent }}
                            >
                              Landlord VPA
                            </Button>
                            <Button
                              type="button"
                              h="48px"
                              borderRadius="16px"
                              borderWidth="1px"
                              bg={rentVerificationMethod === "documents"
                                ? selectedGradient
                                : palette.subCardBg}
                              borderColor={rentVerificationMethod === "documents" ? palette.accent : idleBorder}
                              color={rentVerificationMethod === "documents" ? palette.buttonText : idleCardText}
                              onClick={() => setRentVerificationMethod("documents")}
                              _hover={{ borderColor: palette.accent }}
                            >
                              Document Upload
                            </Button>
                          </Grid>

                          {rentVerificationMethod === "landlord_vpa" && (
                            <FormControl>
                              <Input
                                {...register("landlord_vpa")}
                                placeholder="Landlord VPA"
                                h="52px"
                                borderRadius="16px"
                                bg={palette.inputBg}
                                color={palette.inputText}
                                borderColor={palette.inputBorder}
                                _placeholder={{ color: palette.mutedText }}
                              />
                            </FormControl>
                          )}

                          {rentVerificationMethod === "documents" && (
                            <FormControl>
                              <Input
                                type="file"
                                multiple
                                accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                                onChange={(event) => {
                                  const files = event.target.files ? Array.from(event.target.files) : [];
                                  setRentDocuments(files);
                                }}
                                h="auto"
                                py={3}
                                borderRadius="16px"
                                bg={palette.inputBg}
                                color={palette.inputText}
                                borderColor={palette.inputBorder}
                              />
                              <Text mt={2} color={palette.mutedText} fontSize="sm">
                                Upload rent agreement, receipts, or supporting rent documents.
                              </Text>
                              {rentDocuments.length > 0 && (
                                <VStack mt={3} align="stretch" spacing={2}>
                                  {rentDocuments.map((file) => (
                                    <Text key={`${file.name}-${file.size}`} color={palette.pageText} fontSize="sm">
                                      {file.name}
                                    </Text>
                                  ))}
                                </VStack>
                              )}
                            </FormControl>
                          )}

                          <Button
                            onClick={onVerifyRent}
                            isLoading={isVerifying}
                            loadingText="Verifying"
                            isDisabled={isRentVerified}
                            bg={isRentVerified ? "green.500" : palette.buttonBg}
                            color="white"
                            size="md"
                            borderRadius="14px"
                            mt={2}
                          >
                            {isRentVerified ? "✓ Verified" : "Verify Rent"}
                          </Button>
                        </VStack>
                      )}
                    </VStack>
                  );
                })}
              </Grid>
            </Box>

            <form onSubmit={handleSubmit(onSubmit)}>
              <VStack spacing={5} align="stretch">
                {showUserIdField ? (
                  <FormControl isInvalid={!!errors.user_id}>
                    <FormLabel color={palette.pageText}>User ID</FormLabel>
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
                ) : (
                  <Input
                    {...register("user_id")}
                    type="hidden"
                  />
                )}

                <Button
                  type="submit"
                  isLoading={isSubmitting}
                  h="58px"
                  borderRadius="18px"
                  bg={palette.buttonBg}
                  color={palette.buttonText}
                  fontWeight="bold"
                  _hover={{ bg: palette.buttonHover }}
                >
                  Run AI Evaluation
                </Button>

                <HStack color="#8f856c" fontSize="sm" spacing={3}>
                  <Text>Secure</Text>
                  <Text>•</Text>
                  <Text>Private</Text>
                  <Text>•</Text>
                  <Text>Encrypted</Text>
                </HStack>
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

            {result && (
              <Alert status="success" borderRadius="18px" bg="rgba(26, 83, 46, 0.32)">
                <AlertIcon />
                <Box>
                  <AlertTitle>Evaluation complete</AlertTitle>
                  <AlertDescription>
                    Score {result.axiom_score} generated. Opening next page now.
                  </AlertDescription>
                </Box>
              </Alert>
            )}
          </VStack>
          </Box>
        </InteractiveCard>
      </GridItem>

      {showPipeline && (
        <GridItem>
          <VStack spacing={6} align="stretch">
            <InteractiveCard tilt={4} scale={1.01}>
              <Box p={[6, 8]} borderWidth="1px" borderRadius="30px" bg={palette.cardBg} boxShadow={palette.cardShadow} minH="340px">
              <Text color={palette.accent} letterSpacing="0.18em" fontSize="xs" mb={2}>
                03. AI PIPELINE
              </Text>
              <Text fontSize="2xl" fontWeight="bold" mb={2}>
                AI Evaluation in Progress
              </Text>
              <Text color={palette.mutedText} mb={8}>
                The interface mirrors your wireframe, while the API call still hits the original scoring backend.
              </Text>

              <HStack justify="space-between" align="flex-start" spacing={3} mb={8}>
                {pipelineSteps.map((step, index) => {
                  const active = index <= pipelineStage || result;
                  return (
                    <VStack key={step} spacing={3} flex="1" align="center">
                      <Flex
                        w="62px"
                        h="62px"
                        borderRadius="full"
                        align="center"
                        justify="center"
                        borderWidth="2px"
                        borderColor={active ? palette.accent : idleBorder}
                        color={active ? palette.accent : palette.mutedText}
                      >
                        <Text fontWeight="bold">{index + 1}</Text>
                      </Flex>
                      <Text textAlign="center" fontSize="sm" color={active ? palette.pageText : palette.mutedText}>
                        {step}
                      </Text>
                    </VStack>
                  );
                })}
              </HStack>

              <Box p={5} borderWidth="1px" borderRadius="22px" bg={palette.subCardBg}>
                <Text color={palette.accentSoft} mb={3}>
                  Processing {activeInputLabel}
                </Text>
                <Progress
                  value={progress}
                  size="sm"
                  borderRadius="full"
                  sx={{
                    "& > div": {
                      background: "linear-gradient(90deg, rgba(244,190,75,0.7) 0%, #f6c45a 100%)",
                    },
                  }}
                />
                <Text mt={3} color={palette.mutedText} fontSize="sm">
                  {isSubmitting ? pipelineSteps[pipelineStage] : "Ready to analyze behavioral patterns and trust signals."}
                </Text>
              </Box>
              </Box>
            </InteractiveCard>
          </VStack>
        </GridItem>
      )}
    </Grid>
  );
}
