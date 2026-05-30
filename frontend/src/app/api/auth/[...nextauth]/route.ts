import NextAuth, { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Local Credentials",
      credentials: {
        username: { label: "Username (use 'admin')", type: "text", placeholder: "admin" },
        password: { label: "Password (use 'password')", type: "password" }
      },
      async authorize(credentials) {
        // Mock authentication check for demonstration. 
        // In a real application, check against Prisma/Drizzle (SQLite).
        if (credentials?.username === "admin" && credentials?.password === "password") {
          return { id: "1", name: "Admin Creator", email: "admin@creatorjoy.com" };
        }
        return null;
      }
    })
  ],
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET || "fallback_secret_for_development_only",
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
