import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(req: NextRequest) {
  if (req.nextUrl.pathname.startsWith("/chat")) {
    // Auth via localStorage não cobre SSR; redirecionamento real acontece via client-side guard.
    // Middleware aqui só protege contra acesso direto sem cookie de sessão (fase posterior).
    return NextResponse.next();
  }
  return NextResponse.next();
}

export const config = { matcher: ["/chat/:path*"] };
