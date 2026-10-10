import { create } from "zustand";
import { account, authToken, setAuthToken, type UserInfo } from "@/lib/api";

interface AccountState {
  user: UserInfo | null;
  loaded: boolean;
  load: () => Promise<void>;
  signIn: (token: string, user: UserInfo) => void;
  signOut: () => void;
}

export const useAccount = create<AccountState>((set) => ({
  user: null,
  loaded: false,
  load: async () => {
    if (!authToken()) {
      set({ loaded: true });
      return;
    }
    try {
      set({ user: await account.me(), loaded: true });
    } catch {
      setAuthToken(null);
      set({ user: null, loaded: true });
    }
  },
  signIn: (token, user) => {
    setAuthToken(token);
    set({ user, loaded: true });
  },
  signOut: () => {
    setAuthToken(null);
    set({ user: null });
  },
}));
