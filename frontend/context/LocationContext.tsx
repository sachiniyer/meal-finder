import React, { createContext, useContext, useState, useEffect } from "react";
import { getCookie, setCookie } from "../utils/cookies";

interface Location {
  latitude: number;
  longitude: number;
}

interface LocationContextType {
  location: Location | null;
  isLoading: boolean;
}

const LocationContext = createContext<LocationContextType>({
  location: null,
  isLoading: true,
});

export function LocationProvider({ children }: { children: React.ReactNode }) {
  const [location, setLocation] = useState<Location | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isLoading && !location) {
      // Try to get location from cookie first
      const cachedLocation = getCookie("userLocation");

      if (cachedLocation) {
        try {
          const parsedLocation = JSON.parse(cachedLocation);
          setLocation(parsedLocation);
          setIsLoading(false);
          return;
        } catch (error) {
          console.error("Error parsing cached location:", error);
        }
      }

      // If no cached location, request new location
      console.log("fetching location");
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const newLocation = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          };

          // Cache the location
          setCookie("userLocation", JSON.stringify(newLocation));

          setLocation(newLocation);
          setIsLoading(false);
        },
        (error) => {
          console.log(error);
          setIsLoading(false);
        },
      );
    }
  }, []);

  return (
    <LocationContext.Provider value={{ location, isLoading }}>
      {children}
    </LocationContext.Provider>
  );
}

export const useLocation = () => useContext(LocationContext);
