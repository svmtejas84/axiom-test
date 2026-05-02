import { extendTheme } from "@chakra-ui/react";

export const theme = extendTheme({
  fonts: {
    heading: "'Trebuchet MS', 'Segoe UI', sans-serif",
    body: "'Segoe UI', 'Trebuchet MS', sans-serif",
  },
  styles: {
    global: {
      body: {
        bg: "#f5efe6",
        color: "#231911",
        backgroundImage:
          "radial-gradient(circle at top right, rgba(242, 158, 8, 0.22), transparent 26%), radial-gradient(circle at bottom left, rgba(152, 0, 2, 0.10), transparent 28%), linear-gradient(180deg, #faf6ee 0%, #f4ede3 100%)",
      },
      "*::placeholder": {
        color: "#8f6f54",
      },
      "*": {
        borderColor: "rgba(152, 0, 2, 0.12)",
      },
    },
  },
});
