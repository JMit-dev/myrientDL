"use client";

import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Input,
  Button,
  Select,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  useToast,
} from "@chakra-ui/react";
import { useState } from "react";
import { useSearchGames, useQueueDownload } from "@/lib/hooks/useGames";
import { useCollections, useConsoles } from "@/lib/hooks/useCollections";
import { useStats, useStartCrawl } from "@/lib/hooks/useStats";
import { GameList } from "@/components/GameList";
import { FiSearch, FiDownload, FiRefreshCw } from "react-icons/fi";

export default function Home() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedConsole, setSelectedConsole] = useState("");
  const [selectedCollection, setSelectedCollection] = useState("");
  const [selectedGames, setSelectedGames] = useState<number[]>([]);

  const toast = useToast();

  // Queries
  const { data: stats } = useStats();
  const { data: collections } = useCollections();
  const { data: consoles } = useConsoles();

  // Mutations
  const searchMutation = useSearchGames();
  const downloadMutation = useQueueDownload();
  const crawlMutation = useStartCrawl();

  const handleSearch = () => {
    if (!searchQuery.trim()) {
      toast({
        title: "Enter a search query",
        status: "warning",
        duration: 3000,
      });
      return;
    }

    searchMutation.mutate({
      query: searchQuery,
      console: selectedConsole || undefined,
      collection: selectedCollection || undefined,
      limit: 50,
    });
  };

  const handleDownload = () => {
    if (selectedGames.length === 0) {
      toast({
        title: "Select games to download",
        status: "warning",
        duration: 3000,
      });
      return;
    }

    downloadMutation.mutate(selectedGames, {
      onSuccess: () => {
        toast({
          title: "Download queued",
          description: `${selectedGames.length} game(s) queued for download`,
          status: "success",
          duration: 3000,
        });
        setSelectedGames([]);
      },
      onError: () => {
        toast({
          title: "Download failed",
          status: "error",
          duration: 3000,
        });
      },
    });
  };

  const handleCrawl = () => {
    crawlMutation.mutate(undefined, {
      onSuccess: () => {
        toast({
          title: "Crawl started",
          description: "Started crawling Myrient archive",
          status: "success",
          duration: 3000,
        });
      },
      onError: () => {
        toast({
          title: "Crawl failed",
          status: "error",
          duration: 3000,
        });
      },
    });
  };

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="2xl" mb={2}>
            MyrientDL
          </Heading>
          <Heading size="md" color="gray.600" fontWeight="normal">
            Browse and download games from the Myrient archive
          </Heading>
        </Box>

        {/* Stats */}
        {stats && (
          <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
            <Stat>
              <StatLabel>Total Games</StatLabel>
              <StatNumber>{stats.total_games.toLocaleString()}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel>Downloaded</StatLabel>
              <StatNumber>{stats.downloaded_games.toLocaleString()}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel>Collections</StatLabel>
              <StatNumber>{stats.collections_count}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel>Consoles</StatLabel>
              <StatNumber>{stats.consoles_count}</StatNumber>
            </Stat>
          </SimpleGrid>
        )}

        {/* Search Bar */}
        <VStack spacing={4} align="stretch">
          <HStack>
            <Input
              placeholder="Search games..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSearch()}
              size="lg"
            />
            <Button
              leftIcon={<FiSearch />}
              colorScheme="blue"
              onClick={handleSearch}
              isLoading={searchMutation.isPending}
              size="lg"
            >
              Search
            </Button>
          </HStack>

          <HStack>
            <Select
              placeholder="All Consoles"
              value={selectedConsole}
              onChange={(e) => setSelectedConsole(e.target.value)}
            >
              {consoles?.map((console) => (
                <option key={console} value={console}>
                  {console}
                </option>
              ))}
            </Select>

            <Select
              placeholder="All Collections"
              value={selectedCollection}
              onChange={(e) => setSelectedCollection(e.target.value)}
            >
              {collections?.map((collection) => (
                <option key={collection.name} value={collection.name}>
                  {collection.name} ({collection.game_count})
                </option>
              ))}
            </Select>

            <Button
              leftIcon={<FiRefreshCw />}
              onClick={handleCrawl}
              isLoading={crawlMutation.isPending}
            >
              Crawl
            </Button>
          </HStack>
        </VStack>

        {/* Download Button */}
        {selectedGames.length > 0 && (
          <Button
            leftIcon={<FiDownload />}
            colorScheme="green"
            onClick={handleDownload}
            isLoading={downloadMutation.isPending}
          >
            Download {selectedGames.length} Selected
          </Button>
        )}

        {/* Results */}
        {searchMutation.data && (
          <GameList
            games={searchMutation.data}
            selectedGames={selectedGames}
            onSelectionChange={setSelectedGames}
          />
        )}
      </VStack>
    </Container>
  );
}
