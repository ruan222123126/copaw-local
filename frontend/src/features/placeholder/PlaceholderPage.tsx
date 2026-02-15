interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="placeholder-card">
      <h2>{title}</h2>
      <p>{description}</p>
      <p>该模块已纳入新前端重建计划，当前先提供路由兼容占位。</p>
    </section>
  );
}
