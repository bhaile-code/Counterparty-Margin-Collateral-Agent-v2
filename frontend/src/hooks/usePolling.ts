import { useState, useEffect, useRef } from 'react';

/**
 * Generic polling hook for async operations
 * Polls a function at regular intervals until a stop condition is met
 *
 * @param fetchFn - Async function to call on each poll
 * @param shouldStop - Function that determines when to stop polling based on the data
 * @param interval - Polling interval in milliseconds (default: 2000ms)
 * @returns Object with data, error, and isPolling state
 */
export function usePolling<T>(
  fetchFn: () => Promise<T>,
  shouldStop: (data: T) => boolean,
  interval: number = 2000
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isPolling) {
      return;
    }

    const poll = async () => {
      try {
        const result = await fetchFn();
        setData(result);
        setError(null);

        if (shouldStop(result)) {
          setIsPolling(false);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Polling failed';
        setError(errorMessage);
        setIsPolling(false);
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      }
    };

    // Initial fetch
    poll();

    // Set up interval
    intervalRef.current = setInterval(poll, interval);

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isPolling, interval]);

  const startPolling = () => setIsPolling(true);
  const stopPolling = () => {
    setIsPolling(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
  };

  return {
    data,
    error,
    isPolling,
    startPolling,
    stopPolling
  };
}
