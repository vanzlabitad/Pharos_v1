import type { Config } from "tailwindcss";
import { bg, ink, accent, semantic, border, font } from "./lib/design-tokens";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { bg, ink, accent, ...semantic },
      fontFamily: { display: font.display as unknown as string[], sans: font.body as unknown as string[], mono: font.mono as unknown as string[] },
      borderColor: { hair: border.hair, rule: border.rule, edge: border.edge },
      borderRadius: { sharp: "0", xs: "2px", sm: "4px", md: "6px" },
      fontSize: {
        "data-xs":  ["11px",   { lineHeight: "14px", letterSpacing: "0"        }],
        "data-sm":  ["12.5px", { lineHeight: "18px", letterSpacing: "0"        }],
        "data-md":  ["18px",   { lineHeight: "22px", letterSpacing: "-0.01em"  }],
        "data-lg":  ["28px",   { lineHeight: "30px", letterSpacing: "-0.02em"  }],
        "data-xl":  ["44px",   { lineHeight: "44px", letterSpacing: "-0.03em"  }],
        "data-2xl": ["64px",   { lineHeight: "60px", letterSpacing: "-0.035em" }],
      },
    },
  },
  plugins: [],
};
export default config;
