import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useCommunicationTest } from "@/components/communication/useCommunicationTest";

describe("communication test timeline", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("Agent A walks for 1500ms before the bubble appears", () => {
    const { result } = renderHook(() => useCommunicationTest());
    act(() => result.current.start());
    act(() => vi.advanceTimersByTime(1499));
    expect(result.current.phase).toBe("walking");
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.phase).toBe("talking");
  });

  it("the bubble stays 2500ms, then Agent A walks back and the scene resets", () => {
    const { result } = renderHook(() => useCommunicationTest());
    act(() => result.current.start());
    act(() => vi.advanceTimersByTime(1500));
    act(() => vi.advanceTimersByTime(2500));
    expect(result.current.phase).toBe("returning");
    act(() => vi.advanceTimersByTime(1500));
    expect(result.current.phase).toBe("idle");
  });

  it("clicking again mid-test does not restart the walk", () => {
    const { result } = renderHook(() => useCommunicationTest());
    act(() => result.current.start());
    act(() => vi.advanceTimersByTime(1500));
    act(() => vi.advanceTimersByTime(500));
    act(() => result.current.start());
    expect(result.current.phase).toBe("talking");
  });
});
