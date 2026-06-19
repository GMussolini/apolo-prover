const ACCESS_KEY = "apolo_access";
const REFRESH_KEY = "apolo_refresh";
const USER_KEY = "apolo_user";

export type Usuario = {
  id: number;
  email: string;
  nome: string;
  permissoes: string;
  is_admin: boolean;
};

export const auth = {
  setSession(access: string, refresh: string, usuario: Usuario) {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
    localStorage.setItem(USER_KEY, JSON.stringify(usuario));
  },
  getAccess(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(ACCESS_KEY);
  },
  getRefresh(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(REFRESH_KEY);
  },
  getUsuario(): Usuario | null {
    if (typeof window === "undefined") return null;
    const v = localStorage.getItem(USER_KEY);
    return v ? JSON.parse(v) : null;
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  },
};
