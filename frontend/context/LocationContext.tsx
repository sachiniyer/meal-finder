import React, { createContext, useContext, useState, useEffect } from "react";

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
      console.log("fetching location");
      navigator.geolocation.getCurrentPosition(
        (position) => {
          console.log(position);
          setLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          });
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
