import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";

export async function action({ request }: { request: Request }) {
  const { shop } = await authenticate.webhook(request);

  if (shop) {
    await prisma.shop.updateMany({
      where: { shopDomain: shop },
      data: {
        status: "uninstalled",
        uninstalledAt: new Date(),
      },
    });
  }

  return new Response();
}
