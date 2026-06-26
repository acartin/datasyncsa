"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { NavigationLoadingOverlay } from "@/components/market-watch/navigation-loading-overlay";

type IntradayRadarPaginationProps = {
  previousHref: string;
  nextHref: string;
  previousDisabled: boolean;
  nextDisabled: boolean;
};

export function IntradayRadarPagination({
  previousHref,
  nextHref,
  previousDisabled,
  nextDisabled,
}: IntradayRadarPaginationProps) {
  const router = useRouter();
  const [isNavigating, startNavigation] = useTransition();

  function navigate(href: string) {
    startNavigation(() => {
      router.push(href);
    });
  }

  return (
    <>
      {isNavigating ? <NavigationLoadingOverlay description="Loading the next result page..." /> : null}
      <div className="flex gap-2">
        <Button type="button" variant="outline" disabled={previousDisabled || isNavigating} onClick={() => navigate(previousHref)}>
          Prev
        </Button>
        <Button type="button" variant="outline" disabled={nextDisabled || isNavigating} onClick={() => navigate(nextHref)}>
          Next
        </Button>
      </div>
    </>
  );
}
