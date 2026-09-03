import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArticlePage } from "@/components/ui/ArticlePage";
import { aidePages, findPage } from "@/lib/data/pages";

export function generateStaticParams() {
  return aidePages.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata(props: PageProps<"/aide/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const page = findPage(aidePages, slug);
  if (!page) return {};
  return {
    title: page.title,
    description: page.intro,
    alternates: { canonical: `/aide/${slug}` },
  };
}

export default async function AidePage(props: PageProps<"/aide/[slug]">) {
  const { slug } = await props.params;
  const page = findPage(aidePages, slug);
  if (!page) notFound();
  return <ArticlePage page={page} breadcrumb={{ label: "Aide", href: "/aide/contact" }} />;
}
