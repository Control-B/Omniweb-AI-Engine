import { prisma } from "../db.server";
import { decryptToken, encryptToken } from "./token-crypto.server";

type AdminGraphql = {
  graphql: (query: string, options?: { variables?: Record<string, unknown> }) => Promise<Response>;
};

const CREATE_STOREFRONT_TOKEN = `#graphql
  mutation CreateStorefrontAccessToken($input: StorefrontAccessTokenInput!) {
    storefrontAccessTokenCreate(input: $input) {
      storefrontAccessToken {
        accessToken
        title
      }
      userErrors {
        field
        message
      }
    }
  }
`;

export async function ensureStorefrontAccessToken(input: {
  admin: AdminGraphql;
  shopId: string;
  shopDomain: string;
  encryptedToken?: string | null;
}) {
  const existing = decryptToken(input.encryptedToken);
  if (existing) return existing;

  const response = await input.admin.graphql(CREATE_STOREFRONT_TOKEN, {
    variables: {
      input: {
        title: `Omniweb storefront token for ${input.shopDomain}`,
      },
    },
  });
  const payload = await response.json() as {
    data?: {
      storefrontAccessTokenCreate?: {
        storefrontAccessToken?: { accessToken?: string | null };
        userErrors?: Array<{ message?: string | null }>;
      };
    };
    errors?: unknown;
  };

  const result = payload.data?.storefrontAccessTokenCreate;
  const userErrors = result?.userErrors || [];
  if (payload.errors || userErrors.length > 0) {
    const message = userErrors.map((error) => error.message).filter(Boolean).join("; ");
    throw new Error(message || "Failed to create Storefront API token");
  }

  const token = result?.storefrontAccessToken?.accessToken;
  if (!token) throw new Error("Shopify did not return a Storefront API token");

  await prisma.shop.update({
    where: { id: input.shopId },
    data: { encryptedStorefrontToken: encryptToken(token) },
  });

  return token;
}
