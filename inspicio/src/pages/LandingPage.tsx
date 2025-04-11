import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, ChevronRight } from 'lucide-react'
import { Button } from '../components/ui/button'
import StackingCards from '../components/ui/stacking-cards'
import { StackingCardItem } from '../components/ui/stacking-cards'
import StackingCardsDemo from '../components/stacked-cards-view'

const AnimatedGroup = ({ children, className }: { children: React.ReactNode, className?: string }) => (
  <div className={className}>{children}</div>
)

const TextEffect = ({ children, className, as: Component = 'div' }: 
  { children: React.ReactNode, className?: string, as?: any }) => (
  <Component className={className}>{children}</Component>
)

const Header = () => (
  <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-sm border-b">
    <div className="container mx-auto px-6 py-4 flex justify-between items-center">
      <div className="text-xl font-bold">
        <img src="/src/assets/autolibra_logo.svg" alt="OSW Logo" className="w-auto h-12" />
      </div>
      <nav className="hidden md:flex gap-6">
        <Link to="/" className="hover:text-primary">Home</Link>
        <Link to="/features" className="hover:text-primary">Features</Link>
        <Link to="/about" className="hover:text-primary">About</Link>
        <Link to="/contact" className="hover:text-primary">Contact</Link>
      </nav>
    </div>
  </header>
)

export default function LandingPage() {
  const navigate = useNavigate();
  
  return (
    <>
      <Header />
      <main className="overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-0 isolate hidden opacity-65 lg:block">
          <div className="w-140 h-320 absolute left-0 top-0 -rotate-45 rounded-full bg-[radial-gradient(68.54%_68.72%_at_55.02%_31.46%,hsla(0,0%,85%,.08)_0,hsla(0,0%,55%,.02)_50%,hsla(0,0%,45%,0)_80%)]" />
          <div className="h-320 absolute left-0 top-0 w-60 -rotate-45 rounded-full bg-[radial-gradient(50%_50%_at_50%_50%,hsla(0,0%,85%,.06)_0,hsla(0,0%,45%,.02)_80%,transparent_100%)]" />
          <div className="h-320 absolute left-0 top-0 w-60 -rotate-45 bg-[radial-gradient(50%_50%_at_50%_50%,hsla(0,0%,85%,.04)_0,hsla(0,0%,45%,.02)_80%,transparent_100%)]" />
        </div>
        <section>
          <div className="relative pt-24 md:pt-36">
            <AnimatedGroup className="absolute inset-0 -z-20">
              <img
                src="https://res.cloudinary.com/dg4jhba5c/image/upload/v1741605538/night-background_ni3vqb.jpg"
                alt="background"
                className="absolute inset-x-0 top-56 -z-20 hidden lg:top-32 dark:block"
                width="3276"
                height="4095"
              />
            </AnimatedGroup>
            <div className="absolute inset-0 -z-10 size-full [background:radial-gradient(125%_125%_at_50%_100%,transparent_0%,var(--color-background)_75%)]"></div>
            <div className="mx-auto max-w-7xl px-6">
              <div className="text-center sm:mx-auto lg:mr-auto lg:mt-0">
                <AnimatedGroup>
                  <Link
                    to="#"
                    className="hover:bg-background group mx-auto flex w-fit items-center gap-4 rounded-full border p-1 pl-4 shadow-md transition-colors duration-300">
                    <span className="text-foreground text-sm">Intelligent Evaluation Platform</span>
                    <span className="block h-4 w-0.5 border-l bg-white dark:bg-zinc-700"></span>

                    <div className="bg-background group-hover:bg-muted size-6 overflow-hidden rounded-full duration-500">
                      <div className="flex w-12 -translate-x-1/2 duration-500 ease-in-out group-hover:translate-x-0">
                        <span className="flex size-6">
                          <ArrowRight className="m-auto size-3" />
                        </span>
                        <span className="flex size-6">
                          <ArrowRight className="m-auto size-3" />
                        </span>
                      </div>
                    </div>
                  </Link>
                </AnimatedGroup>

                <div className="mt-8 lg:mt-16 flex justify-center">
                  <img 
                    src="/src/assets/autolibra_logo_text.svg"
                    alt="AutoLibra"
                    className="h-auto w-full max-w-3xl"
                  />
                </div>
                <TextEffect
                  as="p"
                  className="mx-auto mt-8 max-w-2xl text-balance text-lg italic">
                  A powerful tool for evaluating and improving language agents.
                </TextEffect>

                <AnimatedGroup className="mt-12 flex flex-col items-center justify-center gap-2 md:flex-row">
                  <Button
                    className="h-10.5 rounded-xl px-5">
                    <Link to="#learn-more">
                      <span className="text-nowrap">Learn More</span>
                    </Link>
                  </Button>
                </AnimatedGroup>
              </div>
            </div>

            <StackingCardsDemo />
          </div>
        </section>
      </main>
    </>
  )
}
