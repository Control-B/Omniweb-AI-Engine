import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";

export async function action({ request }: { request: Request }) {
  const { shop } = await authenticate.webhook(request);

  if (shop) {
    await prisma.shop.deleteMany({ where: { shopDomain: shop } });
    // TODO: request full tenant deletion from the AI Engine.
  }

  return new Response();
}
