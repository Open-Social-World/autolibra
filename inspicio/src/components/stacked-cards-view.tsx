// author: Khoa Phan <https://www.pldkhoa.dev>

"use client"

import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { cn } from "../lib/utils"
import StackingCards, {
  StackingCardItem,
} from "@/components/ui/stacking-cards"

const cards = [
  {
    bgColor: "bg-black",
    title: "SOTOPIA",
    backgroundImage: "/src/assets/SotopiaMascot.png",
  },
  {
    bgColor: "bg-black",
    title: "WEBARENA",
    backgroundImage: "/src/assets/WebArenaMascot.png",
  },
  {
    bgColor: "bg-black",
    title: "WEBVOYAGER",
    backgroundImage: "/src/assets/WebVoyagerLogo.png",
  },
  {
    bgColor: "bg-black",
    title: "BABA AI",
    backgroundImage: "/src/assets/BabaMascot.gif",
  },
  {
    bgColor: "bg-black",
    title: "BALROG",
    backgroundImage: "/src/assets/BalrogMascot.png",
  },
  {
    bgColor: "bg-black",
    title: "COLLABORATIVE GYM",
    backgroundImage: "/src/assets/CoGymMascot.png",
  },
]

export default function StackingCardsDemo() {
  const [container, setContainer] = useState<HTMLElement | null>(null)
  const navigate = useNavigate()

  const handleCardClick = (title: string) => {
    if (title === "SOTOPIA") {
      navigate("/sotopia")
    } else if (title === "WEBARENA") {
      navigate("/webarena")
    } else if (title === "WEBVOYAGER") {
      navigate("/webvoyager")
    }
  }

  return (
    <div
      className="h-[620px] bg-white overflow-auto text-white"
      ref={(node) => setContainer(node)}
    >
      <StackingCards
        totalCards={cards.length}
        scrollOptons={{ container: { current: container } }}
      >
        <div className="relative font-calendas h-[620px] w-full z-10 text-2xl md:text-7xl font-bold uppercase flex justify-center items-center text-[#ff4f00] whitespace-pre">
          Supported Agent Domains ↓
        </div>
        {cards.map(({ bgColor, backgroundImage, title }, index) => {
          return (
            <StackingCardItem key={index} index={index} className="h-[620px]">
              <div
                className={cn(
                  bgColor,
                  "h-[80%] sm:h-[70%] flex-col sm:flex-row aspect-video px-8 py-10 flex w-11/12 rounded-3xl mx-auto relative transition-all duration-300",
                  (title === "SOTOPIA" || title === "WEBARENA" || title === "WEBVOYAGER")
                    ? "cursor-pointer transform hover:scale-105 hover:shadow-xl hover:brightness-125" 
                    : "hover:brightness-125"
                )}
                style={backgroundImage ? { 
                  backgroundImage: `linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.7)), url(${backgroundImage})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center'
                } : {}}
                onClick={() => handleCardClick(title)}
              >
                <div className="flex-1 flex flex-col justify-center items-center w-full h-full">
                  <h3 className="font-bold text-5xl md:text-7xl text-center h-full flex items-center justify-center">
                    {title}
                    {(title === "SOTOPIA" || title === "WEBARENA" || title === "WEBVOYAGER") && (
                      <span className="ml-3 inline-block">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline-block">
                          <path d="M5 12h14"></path>
                          <path d="m12 5 7 7-7 7"></path>
                        </svg>
                      </span>
                    )}
                  </h3>
                </div>
              </div>
            </StackingCardItem>
          )
        })}

      </StackingCards>
    </div>
  )
}
