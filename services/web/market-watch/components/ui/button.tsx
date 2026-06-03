import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary",
        outline: "border border-border-2 bg-transparent text-ink-secondary hover:border-foreground hover:bg-transparent hover:text-foreground data-[active=true]:border-foreground data-[active=true]:bg-transparent data-[active=true]:text-foreground",
        chip: "h-7 rounded-[6px] border border-border-2 bg-transparent px-3 text-xs font-medium text-ink-secondary hover:border-foreground hover:text-foreground data-[active=true]:border-foreground data-[active=true]:bg-[var(--surface-3)] data-[active=true]:text-foreground",
        ghost: "rounded-none border-b border-transparent bg-transparent px-2 text-ink-secondary hover:text-foreground data-[active=true]:border-primary data-[active=true]:text-foreground"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
